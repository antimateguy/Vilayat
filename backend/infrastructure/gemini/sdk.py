"""Creating the Google Gen AI SDK client, and describing its errors."""

import httpx
from google import genai
from google.genai import errors, types

# httpx is the HTTP library the SDK is built on. Its timeouts and connection
# errors reach us unwrapped, so they are caught next to the SDK's own errors.
SDK_ERRORS = (errors.APIError, httpx.HTTPError)


def create_sdk_client(api_key: str, timeout_seconds: float) -> genai.Client:
    """One client for the text model and the embedding model.

    The SDK never retries on its own: every attempt is a request the free tier
    counts, and each one must pass the daily budget first (infrastructure.budget).
    A failed call falls back in the API; the offline jobs simply run again later.
    """
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=round(timeout_seconds * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def is_daily_quota_error(error: Exception) -> bool:
    """True when the service refused because the day's allowance is used up.

    A 429 also comes back when the per-minute limit is hit, which passes within
    a minute; only the per-day kind names a "PerDay" quota in its details.
    """
    return (
        isinstance(error, errors.APIError)
        and error.code == 429
        and "PerDay" in f"{error.message} {error.details}"
    )


def describe(error: Exception) -> str:
    """A short reason for the log. Never includes the request, so never the key."""
    if isinstance(error, errors.APIError):
        return f"HTTP {error.code}: {error.message}"
    return type(error).__name__
