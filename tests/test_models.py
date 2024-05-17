import pytest
from coordinate_transformation_api.models import Crs as MyCrs


@pytest.mark.parametrize(
    ("authority_identifier", "expectations"),
    [
        ("EPSG:7415", "Amersfoort / RD New + NAP height"),
        ("EPSG:7931", "ETRF2000"),
    ],
)
def test_get_projcrs_from_crs(authority_identifier, expectations):
    crs = MyCrs.from_crs_str(authority_identifier)
    projcrs = crs.get_projcrs()
    assert expectations == projcrs.name
