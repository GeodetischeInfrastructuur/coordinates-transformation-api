import os

import pytest
from geodense.lib import textio_to_geojson


@pytest.fixture()
def test_dir():
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture()
def geometry_collection_bbox(test_dir):
    with open(os.path.join(test_dir, "data", "geometry-collection-bbox.json")) as f:
        return textio_to_geojson(f)


@pytest.fixture()
def feature(test_dir):
    with open(os.path.join(test_dir, "data", "feature.json")) as f:
        return textio_to_geojson(f)


@pytest.fixture()
def feature_collection_geometry_collection(test_dir):
    with open(
        os.path.join(test_dir, "data", "feature-collection-geometry-collection.json")
    ) as f:
        return textio_to_geojson(f)


@pytest.fixture()
def feature_geometry_collection(test_dir):
    with open(os.path.join(test_dir, "data", "feature-geometry-collection.json")) as f:
        return textio_to_geojson(f)


@pytest.fixture()
def polygons(test_dir):
    with open(os.path.join(test_dir, "data", "polygons.json")) as f:
        return textio_to_geojson(f)


@pytest.fixture()
def points(test_dir):
    with open(os.path.join(test_dir, "data", "points.json")) as f:
        return textio_to_geojson(f)
