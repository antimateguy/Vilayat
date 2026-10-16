"""Map layers as GeoJSON: area outlines and hexagon heatmaps."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import CatalogDep, get_map_layer_service, get_transit
from api.errors import INVALID, NOT_FOUND
from api.mappers import area_feature, cell_feature
from api.routes.catalog import CityId
from api.schemas.layers import (
    AreaFeatureCollection,
    CellFeatureCollection,
    TransitLineCollection,
    TransitLineFeature,
    TransitLineProperties,
)
from ports.transit import TransitNetworkSource
from services.lookup import require_city
from services.map_layers import CellMetric, MapLayerService

router = APIRouter(tags=["map layers"])

LayerService = Annotated[MapLayerService, Depends(get_map_layer_service)]
CampusId = Annotated[int | None, Query(ge=1, description="Needed for commute figures.")]


@router.get(
    "/cities/{city_id}/layers/areas",
    response_model=AreaFeatureCollection,
    responses=NOT_FOUND | INVALID,
    summary="Area outlines with the figures used to shade them",
    description="A GeoJSON FeatureCollection, one MultiPolygon per area. "
    "Area boundaries: see the city's sources for attribution.",
)
def area_layer(
    city_id: CityId, service: LayerService, campus_id: CampusId = None
) -> AreaFeatureCollection:
    return AreaFeatureCollection(
        features=[area_feature(shape) for shape in service.areas(city_id, campus_id)]
    )


@router.get(
    "/cities/{city_id}/layers/cells",
    response_model=CellFeatureCollection,
    responses=NOT_FOUND | INVALID,
    summary="Hexagon cells with one value each, for a heatmap",
    description=(
        "A GeoJSON FeatureCollection, one hexagon (H3, resolution 8, about 0.7 km²) per cell. "
        "`metric=commute` gives morning minutes to the campus and needs `campus_id`; "
        "`amenities` counts supermarkets, cafes, libraries and gyms in the cell; "
        "`job_access` is the 0 to 1 score."
    ),
)
def cell_layer(
    city_id: CityId,
    service: LayerService,
    metric: Annotated[CellMetric, Query()],
    campus_id: CampusId = None,
) -> CellFeatureCollection:
    return CellFeatureCollection(
        metric=metric.value,
        features=[cell_feature(value) for value in service.cells(city_id, metric, campus_id)],
    )


@router.get(
    "/cities/{city_id}/layers/transit",
    response_model=TransitLineCollection,
    responses=NOT_FOUND,
    summary="U-Bahn, S-Bahn and tram lines, for an overview of the network",
    description=(
        "A GeoJSON FeatureCollection, one LineString per line through the stops of its "
        "longest trip: a schematic like the network maps at stations, not the exact track. "
        "Built offline from the city's timetable (see the city's sources for attribution)."
    ),
)
def transit_layer(
    city_id: CityId,
    catalog: CatalogDep,
    network: Annotated[TransitNetworkSource, Depends(get_transit)],
) -> TransitLineCollection:
    require_city(catalog, city_id)
    return TransitLineCollection(
        features=[
            TransitLineFeature(
                geometry={
                    "type": "LineString",
                    "coordinates": [[stop.lon, stop.lat] for stop in line.stops],
                },
                properties=TransitLineProperties(
                    label=line.label,
                    mode=line.mode.value,
                    colour=line.colour,
                ),
            )
            for line in network.lines(city_id)
        ]
    )
