import json
import math
from contextlib import nullcontext as does_not_raise

import pytest
from coordinate_transformation_api.util import (
    crs_transform,
    validate_crs_transformed_geojson,
)
from fastapi.exceptions import ResponseValidationError
from geodense.geojson import CrsFeatureCollection
from geojson_pydantic import Feature
from geojson_pydantic.geometries import Geometry, GeometryCollection, parse_geometry_obj
from pydantic import ValidationError

from tests.util import not_raises


def test_bbox_transformed():
    with open("tests/data/geometry.json") as f:
        data = json.load(f)
        geometry = parse_geometry_obj(data)
        geometry_original = parse_geometry_obj(data)

        crs_transform(geometry, "EPSG:28992", "EPSG:4326")

        assert geometry_original.bbox is not None
        assert geometry.bbox is not None
        assert len(geometry_original.bbox) == len(geometry.bbox)
        assert geometry_original.bbox != geometry.bbox


# cs2cs -f %.4f EPSG:28992 EPSG:4326 <<<"138871.518881731899455 597389.993749326560646"
# cs2cs -f %.4f EPSG:28992 OGC:CRS84 <<<"138871.518881731899455 597389.993749326560646"
# TODO: test set EPSG:4326 == OGC:CRS84, but with the 'modified' proj.db this isn't the same.
def test_transform_geometry():
    with open("tests/data/geometry.json") as f:
        data = json.load(f)
        geometry: Geometry = parse_geometry_obj(data)
        geometry_original: Geometry = parse_geometry_obj(data)
        geometry_crs84: Geometry = parse_geometry_obj(data)

        crs_transform(geometry, "EPSG:28992", "EPSG:4326")
        crs_transform(geometry_crs84, "EPSG:28992", "OGC:CRS84")

        geometry_dict = json.loads(geometry.model_dump_json())
        # since axis order is always x,y OGC:CRS84==EPSG:4326 in GeoJSON
        # TODO: quickhack, disable assert
        # assert geometry == geometry_crs84

        # check if input is actually transformed
        assert geometry != geometry_original
        with not_raises(
            ValidationError,
            "could not convert output of transform_request_body to type Geometry: {exc}",
        ):
            parse_geometry_obj(geometry_dict)


def test_transform_feature_geometrycollection():
    with open("tests/data/feature-geometry-collection.json") as f:
        data = json.load(f)

        feature = Feature.model_validate(data)
        feature_original = Feature.model_validate(data)

        crs_transform(feature, "EPSG:28992", "OGC:CRS84")

        feature_dict = json.loads(feature.model_dump_json())
        # check if input is actually transformed
        assert feature != feature_original
        with not_raises(
            ValidationError,
            "could not convert output of transform_request_body to type Feature: {exc}",
        ):
            Feature(**feature_dict)


def test_transform_feature():
    with open("tests/data/feature.json") as f:
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


def test_transform_featurecollection():
    with open("tests/data/polygons.json") as f:
        data = json.load(f)
        fc = CrsFeatureCollection(**data)
        fc_original = CrsFeatureCollection(**data)

        crs_transform(fc, "EPSG:28992", "EPSG:4326")

        fc_dict = json.loads(fc.model_dump_json())
        # check if input is actually transformed
        assert fc != fc_original
        # check if crs is updated in transformed output
        assert fc.crs.properties.name != fc_original.crs.properties.name
        with not_raises(
            ValidationError,
            "could not convert output of transform_request_body to type CrsFeatureCollection: {exc}",
        ):
            CrsFeatureCollection(**fc_dict)


def test_transform_featurecollection_geometrycollection():
    with open("tests/data/feature-collection-geometry-collection.json") as f:
        data = json.load(f)
        fc = CrsFeatureCollection(**data)
        fc_original = CrsFeatureCollection(**data)

        crs_transform(fc, "EPSG:28992", "EPSG:4326")

        fc_dict = json.loads(fc.model_dump_json())
        # check if input is actually transformed
        assert fc != fc_original
        with not_raises(
            ValidationError,
            "could not convert output of transform_request_body to type CrsFeatureCollection: {exc}",
        ):
            CrsFeatureCollection(**fc_dict)


def test_transform_geometrycollection():
    with open("tests/data/geometry-collection.json") as f:
        data = json.load(f)
        gc = GeometryCollection(**data)
        gc_original = GeometryCollection(**data)
        crs_transform(gc, "EPSG:28992", "EPSG:4326")

        gc_dict = json.loads(gc.model_dump_json())
        # check if input is actually transformed
        assert gc != gc_original
        with not_raises(
            ValidationError,
            "could not convert output of transform_request_body to type GeometryCollection: {exc}",
        ):
            GeometryCollection(**gc_dict)


def test_validate_crs_transformed_geojson(feature):
    feature_exc = feature.model_copy(deep=True)
    feature_no_exc = feature.model_copy(deep=True)

    crs_transform(feature_exc, "EPSG:4326", "EPSG:28992")
    with pytest.raises(ResponseValidationError):
        validate_crs_transformed_geojson(feature_exc)

    crs_transform(feature_no_exc, "EPSG:28992", "EPSG:4326")
    with does_not_raise():
        validate_crs_transformed_geojson(feature_no_exc)


def test_2d_with_epoch():
    with open("tests/data/test_2d_with_epoch.json") as f:
        data = json.load(f)
        feature_2d_2000 = Feature(**data)
        feature_2d_2020 = Feature(**data)
        feature_2d_org = Feature(**data)

        crs_transform(feature_2d_2000, "EPSG:3043", "EPSG:32631", 2000)
        crs_transform(feature_2d_2020, "EPSG:3043", "EPSG:32631", 2020)

        assert feature_2d_2000 != feature_2d_org
        assert feature_2d_2020 != feature_2d_org

        coords_2000 = feature_2d_2000.geometry.coordinates
        coords_2020 = feature_2d_2020.geometry.coordinates
        coords_org = feature_2d_org.geometry.coordinates

        dif_2000_org = 0.29
        dif_2020_org = 0.76

        assert (
            round(
                math.sqrt(
                    (
                        (coords_2000[0] - coords_org[0])
                        * (coords_2000[0] - coords_org[0])
                    )
                    + (
                        (coords_2000[1] - coords_org[1])
                        * (coords_2000[1] - coords_org[1])
                    )
                ),
                2,
            )
            == dif_2000_org
        )
        assert (
            round(
                math.sqrt(
                    (
                        (coords_2020[0] - coords_org[0])
                        * (coords_2020[0] - coords_org[0])
                    )
                    + (
                        (coords_2020[1] - coords_org[1])
                        * (coords_2020[1] - coords_org[1])
                    )
                ),
                2,
            )
            == dif_2020_org
        )


def test_wgs_epoch():
    with open("tests/data/test_wgs_epoch.json") as f:
        data = json.load(f)
        feature_2024 = Feature(**data)
        feature_2010 = Feature(**data)
        feature_epoch_none = Feature(**data)

        crs_transform(feature_2024, "EPSG:28992", "EPSG:32631", 2024)
        crs_transform(feature_2010, "EPSG:28992", "EPSG:32631", 2010)
        crs_transform(feature_epoch_none, "EPSG:28992", "EPSG:32631")

        assert feature_2024 != feature_2010
        assert feature_2010 != feature_epoch_none
        assert feature_epoch_none != feature_2024

        coords_2024 = feature_2024.geometry.coordinates
        coords_2010 = feature_2010.geometry.coordinates
        coords_epoch_none = feature_epoch_none.geometry.coordinates

        dif_2024_2010 = 0.34
        dif_2024_epoch_none = 0.86

        assert (
            round(
                math.sqrt(
                    (
                        (coords_2024[0] - coords_2010[0])
                        * (coords_2024[0] - coords_2010[0])
                    )
                    + (
                        (coords_2024[1] - coords_2010[1])
                        * (coords_2024[1] - coords_2010[1])
                    )
                ),
                2,
            )
            == dif_2024_2010
        )
        assert (
            round(
                math.sqrt(
                    (
                        (coords_2024[0] - coords_epoch_none[0])
                        * (coords_2024[0] - coords_epoch_none[0])
                    )
                    + (
                        (coords_2024[1] - coords_epoch_none[1])
                        * (coords_2024[1] - coords_epoch_none[1])
                    )
                ),
                2,
            )
            == dif_2024_epoch_none
        )
