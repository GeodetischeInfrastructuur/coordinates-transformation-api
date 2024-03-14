import pytest
from coordinate_transformation_api.models import Crs
from coordinate_transformation_api.util import transform_coordinates

CRS_LIST = [Crs.from_crs_str(x) for x in ["NSGI:Saba_DPnet_Height", "OGC:CRS84h"]]


@pytest.mark.parametrize(
    ("coordinates", "s_crs", "t_crs", "expectation"),
    [
        (
            "4000.0, 1000.0, 0.0",
            "NSGI:Saba_DPnet_Height",
            "OGC:CRS84h",
            (-63.244194654, 17.627459157, -42.3336),
        ),
        (
            "-63.244194654, 17.627459157, -42.3336",
            "OGC:CRS84h",
            "NSGI:Saba_DPnet_Height",
            (4000.0, 1000.0, 0.0),
        ),
    ],
)
def test_transformed_coordinates(coordinates, s_crs, t_crs, expectation):
    transformed_coordinates = transform_coordinates(
        coordinates, s_crs, t_crs, None, CRS_LIST
    )

    assert transformed_coordinates == expectation
