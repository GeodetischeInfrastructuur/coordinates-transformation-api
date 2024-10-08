import json
import math
from unittest.mock import patch

import pytest
from geodense.geojson import CrsFeatureCollection
from geojson_pydantic import Feature
from geojson_pydantic.geometries import (
    GeometryCollection,
    _GeometryBase,
    parse_geometry_obj,
)
from pydantic import ValidationError

from coordinate_transformation_api.crs_transform import get_transformer
from coordinate_transformation_api.util import (
    crs_transform,
    str_to_crs,
)
from tests.util import not_raises

# TODO: add test to signal user geometries or height have been omitted in case transformation not possible


def test_transformer_object_created_once_while_transforming():
    with open("tests/data/polygons.json") as f:
        data = json.load(f)
        geojson_obj = CrsFeatureCollection(**data)

        with patch(
            "coordinate_transformation_api.crs_transform.get_transformer",
            side_effect=get_transformer,
        ) as get_transformer_call:
            _ = crs_transform(geojson_obj, str_to_crs("EPSG:28992"), str_to_crs("EPSG:4326"))
            get_transformer_call.assert_called_once()


def test_transformer_object_created_thrice_while_transforming_7930_7415():
    with open("tests/data/feature-collection-7930.json") as f:
        data = json.load(f)
        geojson_obj = CrsFeatureCollection(**data)

        with patch(
            "coordinate_transformation_api.crs_transform.get_transformer",
            side_effect=get_transformer,
        ) as get_transformer_call:
            _ = crs_transform(geojson_obj, str_to_crs("EPSG:7930"), str_to_crs("EPSG:7415"))
            # get_transformer is called 3 times, once for horizontal, once for vertical causes exc, exc caught -> one more call to get_tranformer
            expected_call_count = 3
            assert get_transformer_call.call_count == expected_call_count


def test_bbox_transformed():
    with open("tests/data/geometry.json") as f:
        data = json.load(f)
        geometry = parse_geometry_obj(data)
        geometry_t = crs_transform(geometry, str_to_crs("EPSG:28992"), str_to_crs("EPSG:4326"))
        assert geometry.bbox is not None
        assert geometry_t.bbox is not None
        assert len(geometry.bbox) == len(geometry_t.bbox)
        assert geometry.bbox != geometry_t.bbox


# cs2cs -f %.4f EPSG:28992 EPSG:4326 <<<"138871.518881731899455 597389.993749326560646"
# cs2cs -f %.4f EPSG:28992 OGC:CRS84 <<<"138871.518881731899455 597389.993749326560646"
# TODO: test set EPSG:4326 == OGC:CRS84, but with the 'modified' proj.db this isn't the same.
def test_transform_geometry_crs84_is_epsg4326():
    with open("tests/data/geometry.json") as f:
        data = json.load(f)
        geometry = parse_geometry_obj(data)

        geometry_t_4326 = crs_transform(geometry, str_to_crs("EPSG:28992"), str_to_crs("EPSG:4326"))
        geometry_t_crs84 = crs_transform(geometry, str_to_crs("EPSG:28992"), str_to_crs("OGC:CRS84"))

        # check if input is actually transformed
        assert geometry_t_4326.model_dump_json() != geometry.model_dump_json()
        assert geometry_t_crs84.model_dump_json() != geometry.model_dump_json()
        # since axis order is always x,y OGC:CRS84==EPSG:4326 in GeoJSON
        assert geometry_t_4326.model_dump_json() == geometry_t_crs84.model_dump_json()


@pytest.mark.parametrize(
    ("geojson_path", "object_type"),
    [
        ("tests/data/geometry.json", _GeometryBase),
        ("tests/data/feature-geometry-collection.json", Feature),
        ("tests/data/feature.json", Feature),
        ("tests/data/polygons.json", CrsFeatureCollection),
        (
            "tests/data/feature-collection-geometry-collection.json",
            CrsFeatureCollection,
        ),
        ("tests/data/geometry-collection.json", GeometryCollection),
    ],
)
def test_transform_geojson_objects(geojson_path, object_type):
    with open(geojson_path) as f:
        data = json.load(f)

        geojson_obj = parse_geometry_obj(data) if object_type is _GeometryBase else object_type(**data)

        geojson_obj_t = crs_transform(geojson_obj, str_to_crs("EPSG:28992"), str_to_crs("EPSG:4326"))
        geojson_obj_t_dict = json.loads(geojson_obj_t.model_dump_json())

        if object_type is CrsFeatureCollection:
            assert geojson_obj_t.crs.properties.name != geojson_obj.crs.properties.name
        # check if input is actually transformed
        assert geojson_obj_t != geojson_obj

        with not_raises(  # check if we can roundtrip the transformed object without exceptions
            ValidationError,
            "could not convert output of transform_request_body to type"
            + object_type.__name__
            + ": {exc}",  # string concat with + otherwise mypy and ruff complains
        ):
            (
                parse_geometry_obj(geojson_obj_t_dict)
                if object_type is _GeometryBase
                else object_type(**geojson_obj_t_dict)
            )


def test_2d_with_epoch():
    with open("tests/data/test_2d_with_epoch.json") as f:
        data = json.load(f)
        feature = Feature(**data)
        feature_2d_org = crs_transform(feature, str_to_crs("EPSG:3857"), str_to_crs("EPSG:28992"))
        feature_2d_2000 = crs_transform(feature, str_to_crs("EPSG:3857"), str_to_crs("EPSG:28992"), 2000)
        feature_2d_2020 = crs_transform(feature, str_to_crs("EPSG:3857"), str_to_crs("EPSG:28992"), 2020)

        assert feature_2d_2000 != feature_2d_org
        assert feature_2d_2020 != feature_2d_org

        coords_2000 = feature_2d_2000.geometry.coordinates
        coords_2020 = feature_2d_2020.geometry.coordinates
        coords_org = feature_2d_org.geometry.coordinates

        dif_2000_org = 0.39  # 0.29
        dif_2020_org = 1.12  # 0.76

        assert (
            round(
                math.sqrt(
                    ((coords_2000[0] - coords_org[0]) * (coords_2000[0] - coords_org[0]))
                    + ((coords_2000[1] - coords_org[1]) * (coords_2000[1] - coords_org[1]))
                ),
                2,
            )
            == dif_2000_org
        )
        assert (
            round(
                math.sqrt(
                    ((coords_2020[0] - coords_org[0]) * (coords_2020[0] - coords_org[0]))
                    + ((coords_2020[1] - coords_org[1]) * (coords_2020[1] - coords_org[1]))
                ),
                2,
            )
            == dif_2020_org
        )


def test_wm_epoch():
    with open("tests/data/test_wm_epoch.json") as f:
        data = json.load(f)
        feature = Feature(**data)

        feature_2024 = crs_transform(feature, str_to_crs("EPSG:28992"), str_to_crs("EPSG:3857"), 2024)
        feature_2010 = crs_transform(feature, str_to_crs("EPSG:28992"), str_to_crs("EPSG:3857"), 2010)
        feature_epoch_none = crs_transform(feature, str_to_crs("EPSG:28992"), str_to_crs("EPSG:3857"))

        assert feature_2024 != feature_2010
        assert feature_2010 != feature_epoch_none
        assert feature_epoch_none != feature_2024

        coords_2024 = feature_2024.geometry.coordinates
        coords_2010 = feature_2010.geometry.coordinates
        coords_epoch_none = feature_epoch_none.geometry.coordinates

        dif_2024_2010 = 0.55  # 0.34
        dif_2024_epoch_none = 1.4  # 0.86

        assert (
            round(
                math.sqrt(
                    ((coords_2024[0] - coords_2010[0]) * (coords_2024[0] - coords_2010[0]))
                    + ((coords_2024[1] - coords_2010[1]) * (coords_2024[1] - coords_2010[1]))
                ),
                2,
            )
            == dif_2024_2010
        )
        assert (
            round(
                math.sqrt(
                    ((coords_2024[0] - coords_epoch_none[0]) * (coords_2024[0] - coords_epoch_none[0]))
                    + ((coords_2024[1] - coords_epoch_none[1]) * (coords_2024[1] - coords_epoch_none[1]))
                ),
                2,
            )
            == dif_2024_epoch_none
        )
