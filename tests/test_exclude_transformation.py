import pytest
from coordinate_transformation_api.crs_transform import exclude_transformation
from coordinate_transformation_api.util import str_to_crs


@pytest.mark.parametrize(
    ("source_crs", "target_crs", "expectation"),
    [
        ("EPSG:7415", "EPSG:28992", True),
        ("EPSG:28992", "EPSG:7415", False),
        ("NSGI:Saba_DPnet_Height", "EPSG:9289", False),
    ],
)
def test_extract_authority_code(source_crs, target_crs, expectation):
    result = exclude_transformation(str_to_crs(source_crs), str_to_crs(target_crs))

    assert expectation == result
