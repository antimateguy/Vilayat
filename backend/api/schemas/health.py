"""Response schema for the health endpoint."""

from typing import Literal

from pydantic import BaseModel


class CheckResult(BaseModel):
    ok: bool
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, CheckResult]
