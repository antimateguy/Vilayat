"""Choosing the model implementations from the settings (a factory).

The API and the offline jobs both build their model clients here, so the
decision "Gemini, or the stand-in that is always unavailable" is made in one place,
and so is the rule that every request is counted against the daily allowance.
"""

from google import genai
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.ai_disabled import DisabledEmbedder, DisabledLLMClient
from infrastructure.budget import DailyBudget
from infrastructure.db.repositories.usage import PostgresUsageLedger
from infrastructure.gemini.client import GeminiClient
from infrastructure.gemini.embedder import TextPace, create_gemini_embedder
from infrastructure.gemini.sdk import create_sdk_client
from infrastructure.settings import Settings
from ports.embedder import Embedder
from ports.llm import LLMClient
from ports.usage import RequestBudget

JOB_TIMEOUT_SECONDS = 60.0
"""Offline jobs can afford to wait longer for an answer; a web request cannot."""


def text_budget(settings: Settings, sessions: sessionmaker[Session]) -> RequestBudget:
    return DailyBudget(
        PostgresUsageLedger(sessions), settings.gemini_text_model, settings.ai_daily_text_requests
    )


def embedding_budget(settings: Settings, sessions: sessionmaker[Session]) -> RequestBudget:
    return DailyBudget(
        PostgresUsageLedger(sessions),
        settings.gemini_embedding_model,
        settings.ai_daily_embedding_requests,
    )


def create_llm(settings: Settings, budget: RequestBudget, *, for_job: bool = False) -> LLMClient:
    client = _sdk_client(settings, for_job)
    if client is None:
        return DisabledLLMClient()
    return GeminiClient(client, settings.gemini_text_model, budget)


def create_embedder(
    settings: Settings, budget: RequestBudget, *, for_job: bool = False
) -> Embedder:
    client = _sdk_client(settings, for_job)
    if client is None:
        return DisabledEmbedder()
    pace = TextPace(settings.ai_embedding_texts_per_minute) if for_job else None
    return create_gemini_embedder(client, settings.gemini_embedding_model, budget, pace)


def _sdk_client(settings: Settings, for_job: bool) -> genai.Client | None:
    if settings.gemini_api_key is None:
        return None
    return create_sdk_client(
        settings.gemini_api_key.get_secret_value(),
        timeout_seconds=JOB_TIMEOUT_SECONDS if for_job else settings.llm_timeout_seconds,
    )
