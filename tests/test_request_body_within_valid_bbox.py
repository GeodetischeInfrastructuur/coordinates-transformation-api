import pytest
from geodense.geojson import CrsFeatureCollection
from geojson_pydantic import Feature

from coordinate_transformation_api.util import request_body_within_valid_bbox


@pytest.mark.parametrize(
    ("geojson", "source_crs", "expectation"),
    [
        (
            CrsFeatureCollection(
                **{
                    "type": "FeatureCollection",
                    "name": "lijnen",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {},
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [
                                    [156264.9063, 601302.5889, 0.0],
                                    [165681.9644, 605544.3131, 0.0],
                                ],
                            },
                        }
                    ],
                }
            ),
            "EPSG:7415",
            True,
        ),
        (
            Feature(
                **{
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [4000.0, 1000.0, -100.0],
                            [6000.0, 1000.0, 1000.0],
                        ],
                    },
                }
            ),
            "NSGI:Saba_DPnet_Height",
            False,
        ),
    ],
)
def test_request_body_within_valid_bbox(geojson, source_crs, expectation):
    result = request_body_within_valid_bbox(geojson, source_crs)

    assert result == expectation
