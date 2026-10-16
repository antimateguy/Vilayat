"""Health endpoint, used by Docker, the deployment platform and the frontend."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from api.dependencies import get_health_probes
from api.schemas.health import CheckResult, HealthResponse
from ports.health import HealthProbe

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    summary="Say that the API process is up, without touching the database",
    description="For keep-warm pings: it wakes the API but lets an idle database sleep.",
)
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
    summary="Report whether the API and its dependencies are working",
)
def health(
    probes: Annotated[Sequence[HealthProbe], Depends(get_health_probes)],
    response: Response,
) -> HealthResponse:
    results = [probe.check() for probe in probes]
    healthy = all(result.ok for result in results)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if healthy else "unavailable",
        checks={r.name: CheckResult(ok=r.ok, detail=r.detail) for r in results},
    )
