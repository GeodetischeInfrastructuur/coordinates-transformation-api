import pytest
from pyproj import CRS

from coordinate_transformation_api.util import get_precision


@pytest.mark.parametrize(
    ("auth_code", "expectation"),
    [
        ("EPSG:28992", 4),
        ("EPSG:7931", 9),
    ],
)
def test_get_precision(auth_code, expectation):
    result = get_precision(CRS.from_user_input(auth_code))

    assert expectation == result
