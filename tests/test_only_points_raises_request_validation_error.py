from contextlib import nullcontext as does_not_raise

import pytest
from coordinate_transformation_api.util import (
    densify_request_body,
    density_check_request_body,
)
from fastapi.exceptions import RequestValidationError
from geodense.types import GeojsonObject

"""Test to check if input with only points raises a RequestValidationError - for both densify and density_check
"""


@pytest.mark.parametrize(
    ("geojson", "expected"),
    [
        (
            "geometry_collection_bbox",
            does_not_raise(),
        ),  # contains one point, and geometries of other geometry type
        (
            "feature",
            does_not_raise(),
        ),  # contains a polygon
        (
            "points",
            pytest.raises(RequestValidationError),
        ),  # contains only points
    ],
)
def test_density_check_points_raises_request_validation_error(
    geojson, expected, request
):
    gj: GeojsonObject = request.getfixturevalue(geojson)

    with expected:
        density_check_request_body(gj, "EPSG:28992", 10, None)


@pytest.mark.parametrize(
    ("geojson", "expected"),
    [
        (
            "geometry_collection_bbox",
            does_not_raise(),
        ),  # contains one point, and geometries of other geometry type
        (
            "feature",
            does_not_raise(),
        ),  # contains a polygon
        (
            "points",
            pytest.raises(RequestValidationError),
        ),  # contains only points
    ],
)
def test_densify_points_raises_request_validation_error(geojson, expected, request):
    gj: GeojsonObject = request.getfixturevalue(geojson)
    with expected:
        densify_request_body(gj, "EPSG:28992", 10, None)
