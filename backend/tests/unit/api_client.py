"""A test client for the API with every data source replaced by an in-memory fake.

Only the five repository providers, the city registry and the model are
overridden. The routes, schemas, middleware, error handling and services are the
real ones. Without `llm` the AI layer is switched off, as it is with no API key.
"""

import dataclasses
from collections.abc import Sequence

from fastapi.testclient import TestClient

from api.dependencies import (
    get_ai_budgets,
    get_ai_enabled,
    get_areas,
    get_briefings,
    get_catalog,
    get_commute,
    get_embedder,
    get_health_probes,
    get_llm,
    get_places,
    get_registry,
    get_rents,
    get_routes,
    get_settings,
    get_transit,
    get_vector_store,
)
from api.main import create_app
from cities.base import FeedSource, ListingPortal, TransitFeeds
from cities.registry import CityRegistry
from infrastructure.ai_disabled import DisabledEmbedder, DisabledLLMClient
from infrastructure.budget import UnlimitedBudget
from infrastructure.fakes.ai import InMemoryBriefings, InMemoryVectorStore
from infrastructure.fakes.health import FakeHealthProbe
from infrastructure.fakes.routes import InMemoryCommuteRoutes, InMemoryTransit
from infrastructure.settings import Settings
from ports.embedder import Embedder
from ports.llm import LLMClient
from ports.usage import RequestBudget
from ports.vector_store import VectorStore
from tests.unit.engine_world import CITY, Engine, build_engine
from tests.unit.test_cities import minimal_city

V1 = "/api/v1"
TEST_MIN_SIMILARITY = 0.3

TESTVILLE = dataclasses.replace(
    minimal_city(CITY),
    feeds=TransitFeeds(
        gtfs=(
            FeedSource("timetable.zip", "https://example.org/gtfs", "Testville Transit", "CC BY"),
        ),
        streets=FeedSource("streets.osm.pbf", "https://example.org/osm", "OpenStreetMap", "ODbL"),
    ),
    listing_portals=(
        ListingPortal("Flatfinder", "Rooms in shared flats", "https://example.org/testville"),
    ),
)


def make_client(
    *,
    with_places: bool = True,
    rate_limit_per_minute: int = 0,
    ai_rate_limit_per_minute: int = 0,
    raise_server_exceptions: bool = True,
    llm: LLMClient | None = None,
    embedder: Embedder | None = None,
    vector_store: VectorStore | None = None,
    briefings: InMemoryBriefings | None = None,
    budgets: Sequence[RequestBudget] | None = None,
    routes: InMemoryCommuteRoutes | None = None,
) -> tuple[TestClient, Engine]:
    engine = build_engine(with_places=with_places)
    settings = Settings(
        rate_limit_per_minute=rate_limit_per_minute,
        ai_rate_limit_per_minute=ai_rate_limit_per_minute,
        # The toy embedder's similarities are lower than a real model's.
        rag_min_similarity=TEST_MIN_SIMILARITY,
    )
    app = create_app(settings)
    app.dependency_overrides.update(
        {
            get_catalog: lambda: engine.catalog,
            get_areas: lambda: engine.areas,
            get_rents: lambda: engine.rents,
            get_commute: lambda: engine.commute,
            get_places: lambda: engine.places,
            get_routes: lambda: routes or InMemoryCommuteRoutes(),
            get_transit: lambda: InMemoryTransit(),
            get_registry: lambda: CityRegistry([TESTVILLE]),
            get_health_probes: lambda: [FakeHealthProbe()],
            get_llm: lambda: llm or DisabledLLMClient(),
            get_embedder: lambda: embedder or DisabledEmbedder(),
            get_vector_store: lambda: vector_store or InMemoryVectorStore(),
            get_briefings: lambda: briefings or InMemoryBriefings(),
            get_ai_enabled: lambda: llm is not None,
            get_ai_budgets: lambda: budgets or [UnlimitedBudget()],
            get_settings: lambda: settings,
        }
    )
    return TestClient(app, raise_server_exceptions=raise_server_exceptions), engine
