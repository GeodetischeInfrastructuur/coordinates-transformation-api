import pytest
from geojson_pydantic.types import Position3D
from pyproj import CRS

from coordinate_transformation_api.util import transform_coordinates


@pytest.mark.parametrize(
    ("coordinates", "s_crs", "t_crs", "expectation"),
    [
        (
            Position3D(4000.0, 1000.0, 0.0),
            ("NSGI", "Saba_DPnet_Height"),
            ("OGC", "CRS84h"),
            (-63.244194654, 17.627459157, -42.3336),
        ),
        (
            Position3D(-63.244194654, 17.627459157, -42.3336),
            ("OGC", "CRS84h"),
            ("NSGI", "Saba_DPnet_Height"),
            (4000.0, 1000.0, 0.0),
        ),
    ],
)
def test_transformed_coordinates(coordinates, s_crs, t_crs, expectation):
    source_crs = CRS.from_authority(*s_crs)
    target_crs = CRS.from_authority(*t_crs)

    transformed_coordinates = transform_coordinates(coordinates, source_crs, target_crs, None)

    assert transformed_coordinates == expectation
