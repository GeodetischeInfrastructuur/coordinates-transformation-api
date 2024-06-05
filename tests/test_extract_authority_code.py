import pytest
from coordinate_transformation_api.util import extract_authority_code


@pytest.mark.parametrize(
    ("auth_code", "expectation"),
    [
        ("EPSG:7415", ("EPSG", "7415")),
        ("EPSG:7931", ("EPSG", "7931")),
        ("http://www.opengis.net/def/crs/EPSG/0/28992", ("EPSG", "28992")),
    ],
)
def test_extract_authority_code(auth_code, expectation):
    result = extract_authority_code(auth_code)

    assert expectation == result
