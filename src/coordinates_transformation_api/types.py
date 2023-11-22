from geojson_pydantic.types import (
    LineStringCoords,
    MultiLineStringCoords,
    MultiPointCoords,
    MultiPolygonCoords,
    PolygonCoords,
    Position,
)

GeojsonCoordinates = (
    Position
    | PolygonCoords
    | LineStringCoords
    | MultiPointCoords
    | MultiLineStringCoords
    | MultiPolygonCoords
)
CoordinatesType = tuple[float, float] | tuple[float, float, float] | list[float]
