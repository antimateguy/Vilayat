"""Composition root: the one place where concrete classes are chosen and wired.

Routes ask for a port or a service through FastAPI's Depends; the functions here
decide which implementation they get. The chain is

    route -> service -> port (interface) <- repository (PostgreSQL)

Tests replace a provider with `app.dependency_overrides[...]`. Overriding the
five repository providers with in-memory fakes is enough: every service is then
built on the fakes, with no database.
"""

from collections.abc import Iterator, Sequence
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from cities.registry import CityRegistry, discover_cities
from infrastructure.ai import create_embedder, create_llm, embedding_budget, text_budget
from infrastructure.db.engine import create_db_engine
from infrastructure.db.health import PostgresHealthProbe
from infrastructure.db.repositories.areas import PostgresAreaRepository
from infrastructure.db.repositories.briefings import PostgresBriefingRepository
from infrastructure.db.repositories.catalog import PostgresCatalogRepository
from infrastructure.db.repositories.commute import PrecomputedCommuteProvider
from infrastructure.db.repositories.places import PostgresPlacesRepository
from infrastructure.db.repositories.rent import PostgresRentProvider
from infrastructure.db.repositories.routes import PostgresCommuteRouteRepository
from infrastructure.db.repositories.vector_store import PgVectorStore
from infrastructure.db.session import create_session_factory
from infrastructure.settings import Settings
from infrastructure.transit_files import FileTransitNetwork
from ports.areas import AreaRepository
from ports.briefings import BriefingRepository
from ports.catalog import CatalogRepository
from ports.commute import CommuteProvider
from ports.embedder import Embedder
from ports.health import HealthProbe
from ports.llm import LLMClient
from ports.places import PlacesRepository
from ports.rent import RentProvider
from ports.routes import CommuteRouteRepository
from ports.transit import TransitNetworkSource
from ports.usage import RequestBudget
from ports.vector_store import VectorStore
from services.area_detail import AreaDetailService
from services.briefing import BriefingReader
from services.commute_route import CommuteRouteService
from services.comparison import ComparisonService
from services.facts import AreaFactsCollector
from services.intent import IntentService
from services.map_layers import MapLayerService
from services.rag import RagService
from services.ranking import RankingService
from services.search import SearchService
from services.sources import SourcesService

# --- Infrastructure --------------------------------------------------------


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_engine() -> Engine:
    """One engine (one connection pool) for the whole process."""
    return create_db_engine(get_settings().database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return create_session_factory(get_engine())


def get_session() -> Iterator[Session]:
    """One database session per request, closed when the response is done."""
    with get_session_factory()() as session:
        yield session


@lru_cache
def get_registry() -> CityRegistry:
    return discover_cities()


def get_health_probes() -> Sequence[HealthProbe]:
    return [PostgresHealthProbe(get_engine())]


@lru_cache
def get_text_budget() -> RequestBudget:
    """The text model's daily allowance, counted in the database so it is
    shared with the offline jobs and survives a restart."""
    return text_budget(get_settings(), get_session_factory())


@lru_cache
def get_embedding_budget() -> RequestBudget:
    return embedding_budget(get_settings(), get_session_factory())


@lru_cache
def get_llm() -> LLMClient:
    """Gemini when a key is configured, otherwise a stand-in that is always
    unavailable. One client for the whole process."""
    return create_llm(get_settings(), get_text_budget())


@lru_cache
def get_embedder() -> Embedder:
    return create_embedder(get_settings(), get_embedding_budget())


def get_ai_budgets() -> Sequence[RequestBudget]:
    return [get_text_budget(), get_embedding_budget()]


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_ai_enabled(settings: SettingsDep) -> bool:
    return settings.ai_enabled


SessionDep = Annotated[Session, Depends(get_session)]

# --- Ports: which implementation each interface gets ------------------------


def get_catalog(session: SessionDep) -> CatalogRepository:
    return PostgresCatalogRepository(session)


def get_areas(session: SessionDep) -> AreaRepository:
    return PostgresAreaRepository(session)


def get_rents(session: SessionDep) -> RentProvider:
    return PostgresRentProvider(session)


def get_commute(session: SessionDep) -> CommuteProvider:
    return PrecomputedCommuteProvider(session)


def get_places(session: SessionDep) -> PlacesRepository:
    return PostgresPlacesRepository(session)


def get_routes(session: SessionDep) -> CommuteRouteRepository:
    return PostgresCommuteRouteRepository(session)


def get_transit() -> TransitNetworkSource:
    return FileTransitNetwork()


def get_vector_store(session: SessionDep) -> VectorStore:
    return PgVectorStore(session)


def get_briefings(session: SessionDep) -> BriefingRepository:
    return PostgresBriefingRepository(session)


CatalogDep = Annotated[CatalogRepository, Depends(get_catalog)]
AreasDep = Annotated[AreaRepository, Depends(get_areas)]
RentsDep = Annotated[RentProvider, Depends(get_rents)]
CommuteDep = Annotated[CommuteProvider, Depends(get_commute)]
PlacesDep = Annotated[PlacesRepository, Depends(get_places)]
RegistryDep = Annotated[CityRegistry, Depends(get_registry)]
LLMDep = Annotated[LLMClient, Depends(get_llm)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
BriefingsDep = Annotated[BriefingRepository, Depends(get_briefings)]

# --- Services: built from ports only ----------------------------------------


def get_collector(
    areas: AreasDep, rents: RentsDep, commute: CommuteDep, places: PlacesDep
) -> AreaFactsCollector:
    return AreaFactsCollector(areas, rents, commute, places)


CollectorDep = Annotated[AreaFactsCollector, Depends(get_collector)]


def get_search_service(
    catalog: CatalogDep, collector: CollectorDep, commute: CommuteDep
) -> SearchService:
    return SearchService(catalog, collector, commute, RankingService())


def get_comparison_service(
    catalog: CatalogDep, areas: AreasDep, collector: CollectorDep
) -> ComparisonService:
    return ComparisonService(catalog, areas, collector)


def get_area_detail_service(
    catalog: CatalogDep, areas: AreasDep, collector: CollectorDep, commute: CommuteDep
) -> AreaDetailService:
    return AreaDetailService(catalog, areas, collector, commute)


def get_commute_route_service(
    catalog: CatalogDep,
    areas: AreasDep,
    routes: Annotated[CommuteRouteRepository, Depends(get_routes)],
) -> CommuteRouteService:
    return CommuteRouteService(catalog, areas, routes)


def get_map_layer_service(
    catalog: CatalogDep,
    areas: AreasDep,
    collector: CollectorDep,
    commute: CommuteDep,
    places: PlacesDep,
) -> MapLayerService:
    return MapLayerService(catalog, areas, collector, commute, places)


def get_sources_service(
    catalog: CatalogDep, rents: RentsDep, places: PlacesDep, commute: CommuteDep
) -> SourcesService:
    return SourcesService(catalog, rents, places, commute)


# --- AI services: the same pattern, with the model behind a port --------------


def get_intent_service(llm: LLMDep, catalog: CatalogDep) -> IntentService:
    return IntentService(llm, catalog)


def get_rag_service(
    embedder: EmbedderDep, store: VectorStoreDep, llm: LLMDep, settings: SettingsDep
) -> RagService:
    return RagService(embedder, store, llm, settings.rag_min_similarity)


def get_briefing_reader(
    catalog: CatalogDep, areas: AreasDep, collector: CollectorDep, briefings: BriefingsDep
) -> BriefingReader:
    """Reading a stored briefing needs no model, so none is wired in here."""
    return BriefingReader(catalog, areas, collector, briefings)
