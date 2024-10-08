import pytest

from coordinate_transformation_api.crs_transform import (
    build_input_coord,
    get_transformer,
    needs_epoch,
)
from coordinate_transformation_api.util import str_to_crs


# This test needs the modified proj.time.dependent.transformations.db from
# https://github.com/GeodetischeInfrastructuur/transformations/releases to be configured
# for pyproj to run correctly.
# Assumption is that the behaviour of the modified proj.db return multiple transformations
# The first being the most 'accurate' but requiring a epoch for a correct transformation.
# The second not requiring a epoch.
@pytest.mark.parametrize(
    ("source", "target", "epoch", "expectation"),
    [
        ("EPSG:7415", "EPSG:3857", 2013.3, True),
        ("EPSG:7415", "EPSG:3857", None, False),
    ],
)
def test_time_dependant_operation_method(source, target, epoch, expectation):
    assert needs_epoch(get_transformer(str_to_crs(source), str_to_crs(target), epoch)) == expectation


@pytest.mark.parametrize(
    ("coord", "epoch", "expectation"),
    [
        (tuple([1000.0, 1000.0]), 2000.0, tuple([1000.0, 1000.0, 0.0, 2000.0])),
        (tuple([1000.0, 1000.0]), None, tuple([1000.0, 1000.0, None])),
        (tuple([1000.0, 1000.0, 10.0]), 2000.0, tuple([1000.0, 1000.0, 10.0, 2000.0])),
        (tuple([1000.0, 1000.0, 10.0]), None, tuple([1000.0, 1000.0, 10.0, None])),
    ],
)
def test_build_input_coord(coord, epoch, expectation):
    assert build_input_coord(coord, epoch) == expectation
