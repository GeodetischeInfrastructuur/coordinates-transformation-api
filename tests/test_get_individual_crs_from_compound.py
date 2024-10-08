import pytest
from pyproj import CRS

from coordinate_transformation_api.crs_transform import get_individual_crs_from_compound


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
    authorities = get_authorities_id_from_result(get_individual_crs_from_compound(CRS.from_user_input(compound_crs)))
    assert expectation == authorities


def get_authorities_id_from_result(crss: tuple[CRS, CRS]) -> tuple[str, str]:
    result = []
    for crs in crss:
        result.append("{}:{}".format(*crs.to_authority()))

    return tuple(result)
