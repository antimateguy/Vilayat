"""The ID of the request being handled, available anywhere during that request."""

from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return _request_id.get()


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)
