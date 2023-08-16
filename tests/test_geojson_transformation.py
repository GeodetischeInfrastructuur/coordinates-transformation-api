import json

from geojson_pydantic import Feature
from geojson_pydantic.geometries import GeometryCollection, parse_geometry_obj
from pydantic_core import ValidationError
from pyproj import Transformer

from coordinates_transformation_api.models import CrsFeatureCollection
from coordinates_transformation_api.util import transform_request_body


def test_bbox_transformed():
    with open("tests/data/geometry.json") as f:
        data = json.load(f)
        geometry = parse_geometry_obj(data)
        geometry_original = parse_geometry_obj(data)
        transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326")
        transform_request_body(geometry, transformer)
        assert geometry_original.bbox is not None
        assert geometry.bbox is not None
        assert len(geometry_original.bbox) == len(geometry.bbox)
        assert geometry_original.bbox != geometry.bbox


def test_transform_geometry():
    with open("tests/data/geometry.json") as f:
        data = json.load(f)
        geometry = parse_geometry_obj(data)
        geometry_original = parse_geometry_obj(data)
        transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326")
        transform_request_body(geometry, transformer)

        geometry_dict = json.loads(geometry.model_dump_json())
        # check if input is actually transformed
        assert geometry != geometry_original
        try:
            parse_geometry_obj(geometry_dict)
        except ValidationError as exc:
            assert (
                False
            ), f"could not convert output of transform_request_body to type Geometry: {exc}"


def test_transform_feature_geometrycollection():
    with open("tests/data/feature-geometry-collection.json") as f:
        data = json.load(f)
        feature = Feature(**data)
        feature_original = Feature(**data)
        transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326")
        transform_request_body(feature, transformer)
        feature_dict = json.loads(feature.model_dump_json())
        # check if input is actually transformed
        assert feature != feature_original
        try:
            Feature(**feature_dict)
        except ValidationError as exc:
            assert (
                False
            ), f"could not convert output of transform_request_body to type Feature: {exc}"


def test_transform_feature():
    with open("tests/data/feature.json") as f:
        data = json.load(f)
        feature = Feature(**data)
        feature_original = Feature(**data)
        transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326")
        transform_request_body(feature, transformer)
        feature_dict = json.loads(feature.model_dump_json())
        # check if input is actually transformed
        assert feature != feature_original
        try:
            Feature(**feature_dict)
        except ValidationError as exc:
            assert (
                False
            ), f"could not convert output of transform_request_body to type Feature: {exc}"


def test_transform_featurecollection():
    with open("tests/data/polygons.json") as f:
        data = json.load(f)
        fc = CrsFeatureCollection(**data)
        fc_original = CrsFeatureCollection(**data)
        transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326")
        transform_request_body(fc, transformer)
        fc_dict = json.loads(fc.model_dump_json())
        # check if input is actually transformed
        assert fc != fc_original
        # check if crs is updated in transformed output
        assert fc.crs.properties.name != fc_original.crs.properties.name
        try:
            CrsFeatureCollection(**fc_dict)
        except ValidationError as exc:
            assert (
                False
            ), f"could not convert output of transform_request_body to type CrsFeatureCollection: {exc}"


def test_transform_featurecollection_geometrycollection():
    with open("tests/data/feature-collection-geometry-collection.json") as f:
        data = json.load(f)
        fc = CrsFeatureCollection(**data)
        fc_original = CrsFeatureCollection(**data)
        transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326")
        transform_request_body(fc, transformer)

        fc_dict = json.loads(fc.model_dump_json())
        # check if input is actually transformed
        assert fc != fc_original
        try:
            CrsFeatureCollection(**fc_dict)
        except ValidationError as exc:
            assert (
                False
            ), f"could not convert output of transform_request_body to type CrsFeatureCollection: {exc}"


def test_transform_geometrycollection():
    with open("tests/data/geometry-collection.json") as f:
        data = json.load(f)
        gc = GeometryCollection(**data)
        gc_original = GeometryCollection(**data)
        transformer = Transformer.from_crs("EPSG:28992", "EPSG:4326")
        transform_request_body(gc, transformer)

        gc_dict = json.loads(gc.model_dump_json())
        # check if input is actually transformed
        assert gc != gc_original
        try:  # check if output type of transform_request_body equals input type
            GeometryCollection(**gc_dict)
        except ValidationError as exc:
            assert (
                False
            ), f"could not convert output of transform_request_body to type GeometryCollection: {exc}"
