"""Schemas for the AI endpoints."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.common import AreaRef, UnknownValue
from api.schemas.search import EmployerRef
from services.intent import MAX_SENTENCE_LENGTH
from services.rag import MAX_QUESTION_LENGTH


class AiStatusOut(BaseModel):
    enabled: bool = Field(
        description="False when no model is configured. The AI endpoints then answer 503 "
        "and every other endpoint works as usual."
    )
    daily_limit_reached: bool = Field(
        default=False,
        description="True when a model's free daily allowance is used up. The AI features "
        "are then off until `resets_at`.",
    )
    resets_at: datetime | None = Field(
        default=None, description="When the allowance starts again, if it is used up."
    )


class IntentIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "sentence": "I study at TUM, can pay 700 euros and want a short commute.",
                    "city_id": "munich",
                }
            ]
        },
    )

    sentence: str = Field(min_length=3, max_length=MAX_SENTENCE_LENGTH)
    city_id: str | None = Field(
        default=None, description="The city the student is looking at, if any."
    )


class IntentCampusOut(BaseModel):
    id: int
    name: str = Field(examples=["City Campus"])
    university_id: int
    university_short_name: str = Field(examples=["TUM"])


class IntentWeightsOut(BaseModel):
    commute: float
    rent: float
    amenities: float
    job_access: float


class IntentOut(BaseModel):
    """Search settings read from the sentence. `null` means the sentence did not
    mention that setting, so the current one should be kept."""

    understood: bool = Field(description="False when the sentence gave no setting at all.")
    city_id: str | None
    campus: IntentCampusOut | None
    max_rent_eur: int | None
    max_commute_minutes: int | None
    employer: EmployerRef | None
    weights: IntentWeightsOut | None = Field(
        description="All four weights, present only if the sentence stressed or dismissed "
        "a preference. Computed by a fixed rule, not by the model."
    )
    notes: list[str] = Field(
        description="What was assumed, and what was asked for but could not be used.",
        examples=[["Not used: wants a balcony"]],
    )


class AskIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"question": "How soon must I register my address?", "city_id": "berlin"}]
        },
    )

    question: str = Field(min_length=3, max_length=MAX_QUESTION_LENGTH)
    city_id: str | None = Field(
        default=None,
        description="With a city, documents about other cities are left out.",
    )


class CitationOut(BaseModel):
    number: int = Field(description='The number used in the answer text, as in "[1]".')
    title: str = Field(examples=["Registering your address in Berlin"])
    section: str | None = Field(examples=["Deadline and place"])
    passage: str | None = Field(
        description="The text the answer was written from; null when the source's licence "
        "does not allow showing it (follow `source_url` to read it)."
    )
    source_url: str
    retrieved_on: date = Field(description="The day the source was read.")
    city_id: str | None = Field(description="null for a document that applies to every city.")
    is_sample: bool = Field(
        description="True for a note written for this project, not an official text."
    )


class AskOut(BaseModel):
    status: Literal["answered", "no_evidence", "sources_only"] = Field(
        description="`answered`: the text cites the passages listed. "
        "`no_evidence`: the documents do not cover the question; nothing was made up. "
        "`sources_only`: passages were found but no checked answer could be written."
    )
    answer: str
    citations: list[CitationOut]


class BriefingOut(BaseModel):
    text: str = Field(description="Two or three sentences that reword the area's figures.")
    model: str = Field(
        description="The model that wrote the text.", examples=["gemini-3.5-flash-lite"]
    )
    generated_at: datetime
    uses_sample_rent: bool = Field(
        description="True if the rent figure in the text is placeholder data."
    )


class AreaBriefingOut(BaseModel):
    area: AreaRef
    briefing: BriefingOut | UnknownValue = Field(
        description='"UNKNOWN" when no briefing has been written, or when the area\'s figures '
        "changed after it was written."
    )
