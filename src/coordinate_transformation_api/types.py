from typing import TypeAlias

from geojson_pydantic.types import (
    LineStringCoords,
    MultiLineStringCoords,
    MultiPointCoords,
    MultiPolygonCoords,
    PolygonCoords,
    Position,
)
from shapely import GeometryCollection
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

GeojsonCoordinates = (
    Position | PolygonCoords | LineStringCoords | MultiPointCoords | MultiLineStringCoords | MultiPolygonCoords
)
CoordinatesType = tuple[float, float] | tuple[float, float, float] | list[float]


ShapelyGeometry: TypeAlias = (  # noqa: UP040
    Point | Polygon | LineString | MultiLineString | MultiPoint | MultiPolygon | GeometryCollection
)
