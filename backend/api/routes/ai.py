"""The AI layer over HTTP. The model translates and explains; it never ranks."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Path

from api.dependencies import (
    CatalogDep,
    get_ai_budgets,
    get_ai_enabled,
    get_briefing_reader,
    get_intent_service,
    get_rag_service,
)
from api.errors import AI_UNAVAILABLE, INVALID, NOT_FOUND
from api.schemas.ai import (
    AiStatusOut,
    AreaBriefingOut,
    AskIn,
    AskOut,
    BriefingOut,
    CitationOut,
    IntentCampusOut,
    IntentIn,
    IntentOut,
    IntentWeightsOut,
)
from api.schemas.common import AreaRef
from api.schemas.search import EmployerRef
from domain.answer import Citation
from ports.usage import RequestBudget
from services.briefing import BriefingReader
from services.intent import IntentService
from services.lookup import require_city
from services.rag import RagService

router = APIRouter(tags=["ai"])


@router.get(
    "/ai/status",
    response_model=AiStatusOut,
    summary="Say whether the AI features are switched on",
)
def ai_status(
    enabled: Annotated[bool, Depends(get_ai_enabled)],
    budgets: Annotated[Sequence[RequestBudget], Depends(get_ai_budgets)],
) -> AiStatusOut:
    if not enabled:
        return AiStatusOut(enabled=False)
    # Reading the counts spends nothing.
    spent = [status for status in (budget.status() for budget in budgets) if status.reached]
    return AiStatusOut(
        enabled=True,
        daily_limit_reached=bool(spent),
        resets_at=max((status.resets_at for status in spent), default=None),
    )


@router.post(
    "/intent",
    response_model=IntentOut,
    responses=INVALID | AI_UNAVAILABLE,
    summary="Turn a sentence into search settings",
    description=(
        "The model fills in a fixed form; the server then checks every value against the "
        "catalogue and the allowed ranges and drops what does not fit. The result only fills "
        "in the search controls. Send it to `POST /search` to get a ranking: the model takes "
        "no part in that."
    ),
)
def intent(
    body: IntentIn, service: Annotated[IntentService, Depends(get_intent_service)]
) -> IntentOut:
    found = service.parse(body.sentence, body.city_id)
    campus, university = found.campus, found.university
    return IntentOut(
        understood=not found.is_empty,
        city_id=found.city_id,
        campus=IntentCampusOut(
            id=campus.id,
            name=campus.name,
            university_id=university.id,
            university_short_name=university.short_name,
        )
        if campus and university
        else None,
        max_rent_eur=found.max_rent_eur,
        max_commute_minutes=found.max_commute_minutes,
        employer=EmployerRef(id=found.employer.id, name=found.employer.name)
        if found.employer
        else None,
        weights=IntentWeightsOut(**found.weights) if found.weights else None,
        notes=list(found.notes),
    )


@router.post(
    "/ask",
    response_model=AskOut,
    responses=NOT_FOUND | INVALID | AI_UNAVAILABLE,
    summary="Answer a question from the stored documents, with citations",
    description=(
        "The answer is written only from passages of the stored documents and cites them. "
        "If no passage is close enough to the question, the status is `no_evidence` and no "
        "model is called. An answer that cites nothing, or contains a figure that is not in "
        "the passages it cites, is withheld and the passages are returned instead "
        "(`sources_only`)."
    ),
)
def ask(
    body: AskIn,
    service: Annotated[RagService, Depends(get_rag_service)],
    catalog: CatalogDep,
) -> AskOut:
    if body.city_id is not None:
        require_city(catalog, body.city_id)
    answer = service.ask(body.question, body.city_id)
    return AskOut(
        status=answer.status.value,
        answer=answer.text,
        citations=[_citation_out(citation) for citation in answer.citations],
    )


def _citation_out(citation: Citation) -> CitationOut:
    chunk = citation.chunk
    # A chunk's first line is "<document title>: <section heading>".
    first_line, _, passage = chunk.content.partition("\n")
    section = first_line.removeprefix(chunk.title).removeprefix(":").strip()
    return CitationOut(
        number=citation.number,
        title=chunk.title,
        section=section or None,
        passage=passage.strip() if chunk.can_quote else None,
        source_url=chunk.source_url,
        retrieved_on=chunk.retrieved_on,
        city_id=chunk.city_id,
        is_sample=chunk.is_sample,
    )


@router.get(
    "/areas/{area_id}/briefing",
    response_model=AreaBriefingOut,
    responses=NOT_FOUND | INVALID,
    summary="Read the stored briefing of an area",
    description=(
        "A briefing is written offline from the area's rent, amenity and job-access figures "
        "and stored; this endpoint never calls a model. It is returned only while those "
        "figures are still current, so its numbers always match the area's facts."
    ),
)
def area_briefing(
    area_id: Annotated[int, Path(ge=1)],
    reader: Annotated[BriefingReader, Depends(get_briefing_reader)],
) -> AreaBriefingOut:
    area, briefing = reader.get(area_id)
    return AreaBriefingOut(
        area=AreaRef(id=area.id, name=area.name),
        briefing=BriefingOut(
            text=briefing.content,
            model=briefing.model,
            generated_at=briefing.generated_at,
            uses_sample_rent=briefing.facts.get("rent_figure_is_a_placeholder") is True,
        )
        if briefing
        else "UNKNOWN",
    )
