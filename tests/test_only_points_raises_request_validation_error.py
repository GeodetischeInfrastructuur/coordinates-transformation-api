from contextlib import nullcontext as does_not_raise

import pytest
from geodense.types import GeojsonObject

from coordinate_transformation_api.main import CrsEnum, density_check
from coordinate_transformation_api.models import DensifyError, DensityCheckError
from coordinate_transformation_api.util import (
    densify_request_body,
)

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
            pytest.raises(
                DensifyError,
                match=r"cannot run densify on GeoJSON that only contains \(Multi\)Point geometries",
            ),
        ),  # contains only points
    ],
)
def test_densify_points_raises_request_validation_error(geojson, expected, request):
    gj: GeojsonObject = request.getfixturevalue(geojson)
    with expected:
        _ = densify_request_body(
            gj, "EPSG:28992", max_segment_length=10, max_segment_deviation=None
        )


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
            pytest.raises(
                DensityCheckError,
                match=r"GeoJSON contains only \(Multi\)Point geometries",
            ),
        ),  # contains only points
    ],
)
@pytest.mark.asyncio
async def test_density_check_points_raises_request_validation_error(
    geojson, expected, request
):
    gj: GeojsonObject = request.getfixturevalue(geojson)

    with expected:
        _ = await density_check(gj, CrsEnum.EPSG_28992, max_segment_length=10)
