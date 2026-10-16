"""Middleware: request IDs, timing logs and rate limiting.

Written as plain ASGI middleware (no base class), so the request ID set here is
visible to everything that handles the request, including the error handlers.
"""

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.context import set_request_id
from api.errors import error_response
from api.rate_limit import SlidingWindowRateLimiter
from services.timing import recording

logger = logging.getLogger("api.requests")

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """Gives every request an ID, measures it and writes one log line for it.

    The ID is returned in the X-Request-ID header and included in error bodies.
    Stage timings are also returned in the standard Server-Timing header, where
    browser developer tools display them.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        supplied = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        # A caller may pass its own ID to follow a request across systems, but
        # only harmless characters are accepted into our logs.
        request_id = supplied if _SAFE_REQUEST_ID.match(supplied) else uuid.uuid4().hex
        set_request_id(request_id)

        status_code = 500
        started = time.perf_counter()
        with recording() as stages:

            async def send_with_headers(message: Message) -> None:
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    headers = MutableHeaders(scope=message)
                    headers[REQUEST_ID_HEADER] = request_id
                    total = (time.perf_counter() - started) * 1000
                    timings = [*stages, ("total", total)]
                    headers["Server-Timing"] = ", ".join(
                        f"{name};dur={duration:.1f}" for name, duration in timings
                    )
                await send(message)

            try:
                await self._app(scope, receive, send_with_headers)
            finally:
                total = (time.perf_counter() - started) * 1000
                logger.info(
                    "request_id=%s method=%s path=%s status=%d total_ms=%.1f stages=%s",
                    request_id,
                    scope["method"],
                    scope["path"],
                    status_code,
                    total,
                    " ".join(f"{name}={duration:.1f}" for name, duration in stages) or "-",
                )


class RateLimitMiddleware:
    """Refuses a client that sends too many requests in a short time (HTTP 429).

    With `only_paths` the limit covers just those paths. That is how the
    endpoints that call the language model get a second, stricter limit.
    """

    def __init__(
        self,
        app: ASGIApp,
        limiter: SlidingWindowRateLimiter,
        exempt_paths: frozenset[str] = frozenset({"/health"}),
        only_paths: frozenset[str] | None = None,
    ) -> None:
        self._app = app
        self._limiter = limiter
        self._exempt = exempt_paths
        self._only = only_paths

    def _applies_to(self, scope: Scope) -> bool:
        if scope["type"] != "http" or scope["path"] in self._exempt:
            return False
        return self._only is None or scope["path"] in self._only

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._applies_to(scope):
            await self._app(scope, receive, send)
            return

        retry_after = self._limiter.check(self._client(scope))
        if retry_after > 0:
            seconds = max(1, round(retry_after))
            response = error_response(
                429,
                "rate_limited",
                f"Too many requests. Try again in {seconds} seconds.",
                headers={"Retry-After": str(seconds)},
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)

    @staticmethod
    def _client(scope: Scope) -> str:
        # Behind a load balancer (Cloud Run) every connection comes from the
        # balancer; it reports the caller's address in X-Forwarded-For.
        forwarded = Headers(scope=scope).get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"
