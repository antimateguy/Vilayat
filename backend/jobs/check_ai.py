"""Check that the configured models answer: one small call to each.

    uv run python -m jobs.check_ai

Needs GEMINI_API_KEY in .env. It uses four free-tier requests, counted
against the daily allowance like any other, and writes nothing else.
"""

import logging
import sys
import time

from infrastructure.ai import create_embedder, create_llm, embedding_budget, text_budget
from infrastructure.settings import Settings
from jobs.runtime import configure_logging, job_sessions
from ports.embedder import EmbedderUnavailableError
from ports.llm import LLMUnavailableError

logger = logging.getLogger("jobs.check_ai")

QUESTION = "How soon do I have to register my address?"
RELATED = "Anyone who moves into a flat must register the address within two weeks."
UNRELATED = "The cafeteria on the main campus is open from eleven until two."
SCHEMA = {
    "type": "object",
    "properties": {"max_rent_eur": {"type": ["integer", "null"]}},
    "required": ["max_rent_eur"],
}


def main() -> int:
    configure_logging()
    settings = Settings()
    if not settings.ai_enabled:
        logger.error("GEMINI_API_KEY is not set in .env, so the AI layer is switched off")
        return 1

    with job_sessions() as sessions:
        llm = create_llm(settings, text_budget(settings, sessions))
        embedder = create_embedder(settings, embedding_budget(settings, sessions))
        try:
            started = time.perf_counter()
            text = llm.generate_text("Reply with the single word: ready")
            logger.info("%s text reply %r in %.1f s", llm.model_name, text, _since(started))

            started = time.perf_counter()
            reply = llm.generate_json("Extract the rent limit: I can pay 650 euros.", SCHEMA)
            logger.info("%s JSON reply %s in %.1f s", llm.model_name, dict(reply), _since(started))

            started = time.perf_counter()
            related, unrelated = embedder.embed_documents([RELATED, UNRELATED])
            query = embedder.embed_query(QUESTION)
            logger.info(
                "%s: %d dimensions in %.1f s; similarity to the question: "
                "related passage %.2f, unrelated passage %.2f",
                embedder.model_name,
                len(query),
                _since(started),
                _dot(query, related),
                _dot(query, unrelated),
            )
        except (LLMUnavailableError, EmbedderUnavailableError) as error:
            logger.error("a model is unavailable: %s", error)
            return 1
        return 0


def _since(started: float) -> float:
    return time.perf_counter() - started


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Cosine similarity, because both vectors have length 1."""
    return sum(x * y for x, y in zip(a, b, strict=True))


if __name__ == "__main__":
    sys.exit(main())
