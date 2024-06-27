import pytest
from coordinate_transformation_api.util import transform_coordinates
from pyproj import CRS


@pytest.mark.parametrize(
    ("coordinates", "s_crs", "t_crs", "expectation"),
    [
        (
            "4000.0, 1000.0, 0.0",
            ("NSGI", "Saba_DPnet_Height"),
            ("OGC", "CRS84h"),
            (-63.244194654, 17.627459157, -42.3336),
        ),
        (
            "-63.244194654, 17.627459157, -42.3336",
            ("OGC", "CRS84h"),
            ("NSGI", "Saba_DPnet_Height"),
            (4000.0, 1000.0, 0.0),
        ),
        (
            "100000, 300000, 43",
            ("EPSG", "7415"),
            ("EPSG", "7931"),
            (50.687412313, 4.608962491, 88.6033),
        ),
        (
            "50.687412313, 4.608962491, 88.6033",
            ("EPSG", "7931"),
            ("EPSG", "7415"),
            (100000, 300000, 43),
        ),
    ],
)
def test_transformed_coordinates(coordinates, s_crs, t_crs, expectation):
    source_crs = CRS.from_authority(*s_crs)
    target_crs = CRS.from_authority(*t_crs)

    transformed_coordinates = transform_coordinates(
        coordinates, source_crs, target_crs, None
    )

    assert transformed_coordinates == pytest.approx(expectation)
