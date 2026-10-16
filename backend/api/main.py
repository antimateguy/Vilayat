"""FastAPI application factory."""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.dependencies import get_settings
from api.errors import COMMON_ERRORS, register_error_handlers
from api.middleware import REQUEST_ID_HEADER, RateLimitMiddleware, RequestContextMiddleware
from api.rate_limit import SlidingWindowRateLimiter
from api.routes import ai, catalog, commute, health, layers, search
from infrastructure.settings import Settings

API_PREFIX = "/api/v1"
MODEL_PATHS = frozenset({f"{API_PREFIX}/intent", f"{API_PREFIX}/ask"})
"""The endpoints that call the language model on every request."""

DESCRIPTION = """
Ranks neighbourhoods for international students by rent, commute to campus and
part-time job access.

**Conventions**

- A figure that is not known is the string `"UNKNOWN"`. It is never `null` and
  never an estimate.
- Errors always have the shape `{"error": {"code", "message", "request_id", "details"}}`.
- Every response carries an `X-Request-ID` header, and a `Server-Timing` header
  with the time each stage took.
- The ranking is deterministic code. A language model only turns a sentence
  into search settings, answers questions from stored documents and rewords
  figures the engine computed. Without it those features answer 503 or are
  empty, and everything else works.
- Rent figures are area-level estimates and job access is a proxy for where
  employers cluster, not a count of vacancies. `GET /cities/{city_id}/sources`
  lists every dataset with its publisher, licence and date.
"""

TAGS = [
    {"name": "catalog", "description": "Cities, universities, campuses, employers, data sources."},
    {"name": "search", "description": "Rank areas for a campus and a budget."},
    {"name": "areas", "description": "One area in detail."},
    {"name": "comparison", "description": "Feasible areas per university for one budget."},
    {"name": "map layers", "description": "GeoJSON for the map."},
    {
        "name": "ai",
        "description": "Sentence search, questions answered from documents, area briefings. "
        "Optional: without a model these answer 503 or are empty, and the rest is unaffected.",
    },
    {"name": "health", "description": "Service status."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    # The HTTP library logs every call to the model; the request log already
    # records the time each stage took.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = FastAPI(
        title="EduCommute Matrix API",
        version="1.0.0",
        description=DESCRIPTION,
        openapi_tags=TAGS,
    )
    register_error_handlers(app)

    # Middleware added later wraps middleware added earlier, so the request
    # context is outermost: every response, including a 429, gets a request ID.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.ai_rate_limit_per_minute > 0:
        # A second, stricter limit: each of these calls uses the model's free quota.
        app.add_middleware(
            RateLimitMiddleware,
            limiter=SlidingWindowRateLimiter(settings.ai_rate_limit_per_minute, window_seconds=60),
            only_paths=MODEL_PATHS,
        )
    if settings.rate_limit_per_minute > 0:
        app.add_middleware(
            RateLimitMiddleware,
            limiter=SlidingWindowRateLimiter(settings.rate_limit_per_minute, window_seconds=60),
        )
    # The frontend is a static site on another origin, so the browser needs CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER, "Server-Timing", "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)

    # /health stays unversioned: Docker and the hosting platform call it.
    app.include_router(health.router)
    v1 = APIRouter(prefix=API_PREFIX, responses=COMMON_ERRORS)
    for module in (catalog, search, commute, layers, ai):
        v1.include_router(module.router)
    app.include_router(v1)
    return app


app = create_app()
