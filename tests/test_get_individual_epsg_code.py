import pytest
from coordinate_transformation_api.crs_transform import get_individual_epsg_code
from pyproj import CRS


@pytest.mark.parametrize(
    ("compound_crs", "expectation"),
    [
        (
            "EPSG:7415",
            (
                "EPSG:28992",
                "EPSG:5709",
            ),
        ),
        (
            "EPSG:7931",
            (
                "EPSG:7931",
                "EPSG:7931",
            ),
        ),
    ],
)
def test_time_dependant_operation_method(compound_crs, expectation):
    assert expectation == get_individual_epsg_code(CRS.from_user_input(compound_crs))
