"""The AI layer's storage on PostgreSQL: documents in pgvector, briefings in a table.

The model and the embedder are fakes, so these tests need the database but no
network and no key.
"""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from domain.briefing import AreaBriefing, BriefingFacts
from infrastructure.db.models import AiUsageRow, AreaBriefingRow, DocChunkRow
from infrastructure.db.repositories.areas import PostgresAreaRepository
from infrastructure.db.repositories.briefings import PostgresBriefingRepository
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.commute import PrecomputedCommuteProvider
from infrastructure.db.repositories.places import PostgresPlacesRepository
from infrastructure.db.repositories.rent import PostgresRentProvider
from infrastructure.db.repositories.usage import PostgresUsageLedger
from infrastructure.db.repositories.vector_store import PgVectorStore
from infrastructure.fakes.ai import ScriptedLLMClient, WordEmbedder
from jobs.build_briefings import run as build_briefings
from jobs.ingest_documents import run as ingest_documents
from services.briefing import BriefingReader
from services.facts import AreaFactsCollector
from tests.integration.world import World, build_world

pytestmark = pytest.mark.integration

REGISTRATION = """\
---
title: Registering your address
source_url: https://example.org/registration
retrieved_on: 2026-10-06
city: {city}
is_sample: true
---
## Deadline

You must register your address within 14 days of moving in.

## Documents

Bring your passport and the confirmation from your landlord.
"""
INSURANCE = """\
---
title: Health insurance
source_url: https://example.org/insurance
retrieved_on: 2026-10-06
city:
is_sample: false
---
## Who needs it

Every student must have health insurance before enrolling.
"""


@pytest.fixture
def world(session: Session) -> World:
    return build_world(session)


@pytest.fixture
def folder(tmp_path: Path, world: World) -> Path:
    (tmp_path / "registration.md").write_text(
        REGISTRATION.format(city=world.city_id), encoding="utf-8"
    )
    (tmp_path / "insurance.md").write_text(INSURANCE, encoding="utf-8")
    return tmp_path


def chunk_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(DocChunkRow)) or 0


def test_documents_are_chunked_embedded_and_found_by_meaning(
    session: Session, folder: Path, world: World
) -> None:
    embedder = WordEmbedder()

    report = ingest_documents(session, embedder, folder)

    assert (report.documents, report.chunks) == (2, 3)
    question = embedder.embed_query("within how many days must I register my address")
    best = PgVectorStore(session).search(question, limit=1, model=embedder.model_name)[0]
    assert best.chunk.content.startswith("Registering your address: Deadline")
    assert (best.chunk.city_id, best.chunk.is_sample) == (world.city_id, True)
    assert best.similarity > 0.3


def test_running_the_job_again_replaces_and_removes_documents(
    session: Session, folder: Path
) -> None:
    embedder = WordEmbedder()
    ingest_documents(session, embedder, folder)

    (folder / "insurance.md").unlink()
    registration = (folder / "registration.md").read_text(encoding="utf-8")
    (folder / "registration.md").write_text(registration.split("## Documents")[0], encoding="utf-8")
    report = ingest_documents(session, embedder, folder)

    assert (report.documents, report.chunks, report.removed) == (1, 1, ("insurance",))
    assert chunk_count(session) == 1
    assert PgVectorStore(session).document_keys() == {"registration"}


def test_a_document_for_an_unknown_city_stops_the_job_before_anything_changes(
    session: Session, folder: Path
) -> None:
    ingest_documents(session, WordEmbedder(), folder)
    (folder / "atlantis.md").write_text(REGISTRATION.format(city="atlantis"), encoding="utf-8")

    with pytest.raises(ValueError, match="no city with id 'atlantis'"):
        ingest_documents(session, WordEmbedder(), folder)

    assert chunk_count(session) == 3


# --- Briefings -------------------------------------------------------------------------


# The three areas of the fixture, in the name order the job handles them.
AREA_TEXTS = [
    f"{name} is described without figures." for name in ("Altstadt", "Nordend", "Ostpark")
]


def briefing_reader(session: Session) -> BriefingReader:
    areas = PostgresAreaRepository(session)
    collector = AreaFactsCollector(
        areas,
        PostgresRentProvider(session),
        PrecomputedCommuteProvider(session),
        PostgresPlacesRepository(session),
    )
    return BriefingReader(
        PostgresCatalogRepository(session), areas, collector, PostgresBriefingRepository(session)
    )


def test_a_briefing_is_stored_and_replaced_per_area(session: Session, world: World) -> None:
    repository = PostgresBriefingRepository(session)
    when = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    facts: BriefingFacts = {
        "neighbourhood": "Altstadt",
        "typical_monthly_rent_eur": 800,
        "placeholder": False,
    }

    assert repository.get(world.altstadt) is None
    repository.save(AreaBriefing(world.altstadt, "First text.", facts, "model-a", when))
    repository.save(AreaBriefing(world.altstadt, "Second text.", facts, "model-b", when))

    assert repository.get(world.altstadt) == AreaBriefing(
        world.altstadt, "Second text.", facts, "model-b", when
    )
    assert session.scalar(select(func.count()).select_from(AreaBriefingRow)) == 1


def test_the_job_writes_briefings_that_the_reader_then_returns(
    session: Session, world: World
) -> None:
    llm = ScriptedLLMClient(*AREA_TEXTS, model_name="scripted-model")

    report = build_briefings(session, llm, world.city_id)
    again = build_briefings(session, ScriptedLLMClient(), world.city_id)

    assert sorted(report.written) == ["Altstadt", "Nordend", "Ostpark"]
    assert (again.written, len(again.unchanged)) == ([], 3)
    # The facts come back from the JSON column equal to freshly computed ones,
    # so the briefing counts as current.
    area, briefing = briefing_reader(session).get(world.altstadt)
    assert area.name == "Altstadt"
    assert briefing is not None
    assert (briefing.content, briefing.model) == (AREA_TEXTS[0], "scripted-model")
    assert briefing.facts["typical_monthly_rent_eur"] != "unknown"


def test_an_area_with_no_data_still_gets_facts_that_say_unknown(
    session: Session, world: World
) -> None:
    llm = ScriptedLLMClient(*AREA_TEXTS)
    build_briefings(session, llm, world.city_id)

    ostpark = PostgresBriefingRepository(session).get(world.ostpark)

    assert ostpark is not None
    assert ostpark.facts["typical_monthly_rent_eur"] == "unknown"
    assert "typical monthly rent in EUR: unknown" in llm.prompts[-1]


# --- Daily allowance ------------------------------------------------------------


@pytest.fixture
def ledger(engine: Engine) -> Iterator[PostgresUsageLedger]:
    # The ledger commits in transactions of its own, so its rows are removed here.
    yield PostgresUsageLedger(sessionmaker(engine))
    with engine.begin() as connection:
        connection.execute(delete(AiUsageRow))


def test_the_ledger_never_hands_out_more_than_the_limit_even_at_once(
    ledger: PostgresUsageLedger,
) -> None:
    day = date(2026, 10, 16)
    with ThreadPoolExecutor(max_workers=8) as pool:
        granted = list(pool.map(lambda _: ledger.take("flash-test", day, 5), range(20)))

    assert granted.count(True) == 5
    assert ledger.used("flash-test", day) == 5
    assert ledger.used("flash-test", date(2026, 10, 17)) == 0
    assert ledger.used("other-model", day) == 0


def test_using_up_the_day_stops_further_requests(ledger: PostgresUsageLedger) -> None:
    day = date(2026, 10, 16)
    ledger.take("flash-test", day, 500)

    ledger.use_up("flash-test", day, 500)

    assert ledger.used("flash-test", day) == 500
    assert ledger.take("flash-test", day, 500) is False


def test_several_requests_are_taken_together_or_not_at_all(ledger: PostgresUsageLedger) -> None:
    day = date(2026, 10, 16)

    assert ledger.take("embedding-test", day, 100, units=90) is True
    assert ledger.take("embedding-test", day, 100, units=16) is False
    assert ledger.used("embedding-test", day) == 90
    assert ledger.take("embedding-test", day, 100, units=10) is True
    assert ledger.used("embedding-test", day) == 100
