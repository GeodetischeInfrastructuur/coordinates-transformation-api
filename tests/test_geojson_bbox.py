import json

from geodense.lib import traverse_geojson_geometries
from geojson_pydantic import Feature
from pydantic import ValidationError
from pyproj import CRS

from coordinate_transformation_api.util import (
    crs_transform,
    update_bbox,
)
from tests.util import not_raises


def test_feature_bbox():
    with open("tests/data/feature-bbox.json") as f:
        data = json.load(f)
        feature = Feature(**data)

        feature_t = crs_transform(
            feature,
            CRS.from_authority(*"EPSG:28992".split(":")),
            CRS.from_authority(*"EPSG:4326".split(":")),
        )

        feature_dict = json.loads(feature.model_dump_json())
        # check if input is actually transformed
        assert feature_t != feature
        with not_raises(
            ValidationError,
            "could not convert output of transform_request_body to type Feature: {exc}",
        ):
            Feature(**feature_dict)


def test_update_bbox(geometry_collection_bbox):
    test_bbox_fc = (138871.518882, 592678.040025, 165681.964476, 605544.313164)
    test_bbox_fc_ft0 = (138871.518882, 592678.040025, 165681.964476, 605544.313164)
    test_bbox_fc_ft0_geom0 = (
        156264.906360,
        601302.588919,
        165681.964476,
        605544.313164,
    )
    test_bbox_fc_ft0_geom1 = (
        138871.518882,
        592678.040025,
        145468.022542,
        597849.345781,
    )
    test_bbox_fc_ft1 = (146835.981928, 599898.553943, 146835.981928, 599898.553943)
    test_bbox_fc_ft1_geom = test_bbox_fc_ft1

    geometry_collection_bbox_t = traverse_geojson_geometries(geometry_collection_bbox, None, update_bbox)

    bbox_fc = tuple(round(x, 6) for x in geometry_collection_bbox_t.bbox)
    assert bbox_fc == test_bbox_fc

    bbox_fc_ft0 = tuple(round(x, 6) for x in geometry_collection_bbox_t.features[0].bbox)
    assert bbox_fc_ft0 == test_bbox_fc_ft0

    bbox_fc_ft0_geom0 = tuple(round(x, 6) for x in geometry_collection_bbox_t.features[0].geometry.geometries[0].bbox)
    assert bbox_fc_ft0_geom0 == test_bbox_fc_ft0_geom0

    bbox_fc_ft0_geom1 = tuple(round(x, 6) for x in geometry_collection_bbox_t.features[0].geometry.geometries[1].bbox)
    assert bbox_fc_ft0_geom1 == test_bbox_fc_ft0_geom1

    bbox_fc_ft1 = tuple(round(x, 6) for x in geometry_collection_bbox_t.features[1].bbox)
    assert bbox_fc_ft1 == test_bbox_fc_ft1

    bbox_fc_ft1_geom = tuple(round(x, 6) for x in geometry_collection_bbox_t.features[1].geometry.bbox)
    assert bbox_fc_ft1_geom == test_bbox_fc_ft1_geom
