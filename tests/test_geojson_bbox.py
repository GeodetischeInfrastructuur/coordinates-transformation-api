import json

from coordinates_transformation_api.models import CrsFeatureCollection
from coordinates_transformation_api.util import (
    crs_transform,
    update_bbox_geojson_object,
)
from geojson_pydantic import Feature
from pydantic import ValidationError

from tests.util import not_raises


def test_feature_bbox():
    with open("tests/data/feature-bbox.json") as f:
        data = json.load(f)
        feature = Feature(**data)
        feature_original = Feature(**data)

        crs_transform(feature, "EPSG:28992", "EPSG:4326")

        feature_dict = json.loads(feature.model_dump_json())
        # check if input is actually transformed
        assert feature != feature_original
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

    json_obj = json.loads(geometry_collection_bbox)
    fc = CrsFeatureCollection(**json_obj)
    update_bbox_geojson_object(fc)

    bbox_fc = tuple(round(x, 6) for x in fc.bbox)
    assert bbox_fc == test_bbox_fc

    bbox_fc_ft0 = tuple(round(x, 6) for x in fc.features[0].bbox)
    assert bbox_fc_ft0 == test_bbox_fc_ft0

    bbox_fc_ft0_geom0 = tuple(
        round(x, 6) for x in fc.features[0].geometry.geometries[0].bbox
    )
    assert bbox_fc_ft0_geom0 == test_bbox_fc_ft0_geom0

    bbox_fc_ft0_geom1 = tuple(
        round(x, 6) for x in fc.features[0].geometry.geometries[1].bbox
    )
    assert bbox_fc_ft0_geom1 == test_bbox_fc_ft0_geom1

    bbox_fc_ft1 = tuple(round(x, 6) for x in fc.features[1].bbox)
    assert bbox_fc_ft1 == test_bbox_fc_ft1

    bbox_fc_ft1_geom = tuple(round(x, 6) for x in fc.features[1].geometry.bbox)
    assert bbox_fc_ft1_geom == test_bbox_fc_ft1_geom
