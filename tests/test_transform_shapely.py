import pytest
from geodense.types import GeojsonObject
from shapely import GeometryCollection as ShpGeometryCollection
from shapely.geometry import MultiPolygon as ShpMultiPolygon
from shapely.geometry import Point as ShpPoint
from shapely.geometry import Polygon as ShpPolygon

from coordinate_transformation_api.crs_transform import (
    get_shapely_objects,
)


@pytest.mark.parametrize(
    ("geojson", "expected"),
    [
        ("geometry_collection_bbox", [ShpGeometryCollection, ShpPoint]),
        ("feature", [ShpPolygon]),
        (
            "polygons",
            [
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
                ShpPolygon,
            ],
        ),
        (
            "feature_collection_geometry_collection",
            [ShpMultiPolygon, ShpGeometryCollection],
        ),
    ],
)
def test_get_shapely_objects(geojson, expected, request):
    gj: GeojsonObject = request.getfixturevalue(geojson)
    result = get_shapely_objects(gj)

    for item, excepted_type in zip(result, expected):
        assert isinstance(item, excepted_type)
