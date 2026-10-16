"""In-memory stand-ins for the stored journeys and the transit network."""

from collections.abc import Sequence

from domain.geo import Coordinate
from domain.route import CommuteRoute, CommuteSpread, DestinationRoute, LegMode
from domain.transit import TransitLine
from ports.routes import CommuteRouteRepository
from ports.transit import TransitNetworkSource


class InMemoryCommuteRoutes(CommuteRouteRepository):
    def __init__(
        self,
        routes: dict[tuple[int, int], CommuteRoute] | None = None,
        spreads: dict[tuple[int, int], CommuteSpread] | None = None,
        transfers: dict[tuple[int, int], DestinationRoute] | None = None,
    ) -> None:
        self.routes = routes or {}
        self.spreads = spreads or {}
        self.transfers = transfers or {}

    def between(self, from_destination_id: int, to_destination_id: int) -> DestinationRoute | None:
        return self.transfers.get((from_destination_id, to_destination_id))

    def route(self, area_id: int, destination_id: int) -> CommuteRoute | None:
        return self.routes.get((area_id, destination_id))

    def spread(self, area_id: int, destination_id: int) -> CommuteSpread | None:
        return self.spreads.get((area_id, destination_id))


class InMemoryTransit(TransitNetworkSource):
    """Testville has one U-Bahn line."""

    def lines(self, city_id: str) -> Sequence[TransitLine]:
        stops = (Coordinate(48.10, 11.50), Coordinate(48.12, 11.55))
        return (
            [TransitLine("U1", LegMode.SUBWAY, "#3C7233", stops)] if city_id == "testville" else []
        )
