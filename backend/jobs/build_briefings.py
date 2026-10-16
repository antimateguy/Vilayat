"""Write and store the briefing of every area.

    uv run python -m jobs.build_briefings --city munich
    uv run python -m jobs.build_briefings --city berlin --limit 20
    uv run python -m jobs.build_briefings --city berlin --written-before 2026-10-16T12:00+00:00

The engine's figures for an area (rent, amenities, job access) are given to the
model, which puts them into two or three sentences. A text that misspells the
area's name, or contains a figure or a name that was not in its input, is
rejected; the model gets one more try, and if that fails nothing is stored.

The job only writes briefings for areas whose figures changed since their last
one, so it can be run again at any time: after new data is loaded, or to carry
on after the model's free quota ran out. Each briefing is committed as soon as
it is written. Needs GEMINI_API_KEY.
"""

import argparse
import logging
import sys
import time
from datetime import datetime

from sqlalchemy.orm import Session

from infrastructure.ai import create_llm, text_budget
from infrastructure.db.engine import create_db_engine
from infrastructure.db.repositories.areas import PostgresAreaRepository
from infrastructure.db.repositories.briefings import PostgresBriefingRepository
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.commute import PrecomputedCommuteProvider
from infrastructure.db.repositories.places import PostgresPlacesRepository
from infrastructure.db.repositories.rent import PostgresRentProvider
from infrastructure.db.session import create_session_factory
from infrastructure.settings import Settings
from jobs.runtime import configure_logging
from ports.llm import LLMClient
from services.briefing import BriefingReport, BriefingWriter
from services.errors import NotFoundError
from services.facts import AreaFactsCollector

logger = logging.getLogger("jobs.build_briefings")

DEFAULT_PAUSE_SECONDS = 4.0
"""Between model calls, to stay inside the free tier's requests per minute."""


def run(
    session: Session,
    llm: LLMClient,
    city_id: str,
    *,
    force: bool = False,
    written_before: datetime | None = None,
    limit: int | None = None,
    pause_seconds: float = 0.0,
) -> BriefingReport:
    collector = AreaFactsCollector(
        PostgresAreaRepository(session),
        PostgresRentProvider(session),
        PrecomputedCommuteProvider(session),
        PostgresPlacesRepository(session),
    )
    writer = BriefingWriter(
        llm,
        PostgresCatalogRepository(session),
        collector,
        PostgresBriefingRepository(session),
    )

    def keep_and_pause() -> None:
        # Committing after each briefing keeps the work done so far if a later
        # call fails, and no model call is ever paid for twice.
        session.commit()
        time.sleep(pause_seconds)

    report = writer.refresh_city(
        city_id,
        force=force,
        written_before=written_before,
        limit=limit,
        after_each=keep_and_pause,
    )
    session.commit()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--city", required=True, help="city id, for example munich")
    parser.add_argument("--force", action="store_true", help="rewrite briefings that are current")
    parser.add_argument(
        "--written-before",
        type=datetime.fromisoformat,
        metavar="WHEN",
        help="also rewrite briefings written before this time, e.g. 2026-10-16T12:00+00:00",
    )
    parser.add_argument("--limit", type=int, help="most areas to attempt in this run")
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_SECONDS, metavar="SECONDS")
    arguments = parser.parse_args()

    configure_logging()
    settings = Settings()
    if not settings.ai_enabled:
        logger.error("GEMINI_API_KEY is not set in .env; briefings cannot be written without it")
        return 1

    engine = create_db_engine(settings.database_url)
    sessions = create_session_factory(engine)
    try:
        with sessions() as session:
            report = run(
                session,
                create_llm(settings, text_budget(settings, sessions), for_job=True),
                arguments.city,
                force=arguments.force,
                written_before=arguments.written_before,
                limit=arguments.limit,
                pause_seconds=arguments.pause,
            )
    except NotFoundError as error:
        logger.error("%s", error)
        return 1
    finally:
        engine.dispose()

    logger.info(
        "%s: %d written, %d already current, %d rejected, %d left",
        arguments.city,
        len(report.written),
        len(report.unchanged),
        len(report.rejected),
        len(report.not_reached),
    )
    for name, problem in report.rejected.items():
        logger.warning("rejected %s: %s", name, problem)
    if report.stopped_because:
        logger.warning("the model stopped answering (%s); run again later", report.stopped_because)
    return 0 if not report.stopped_because else 1


if __name__ == "__main__":
    sys.exit(main())
