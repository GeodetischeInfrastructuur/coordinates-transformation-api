import os

import pytest


@pytest.fixture()
def test_dir():
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture()
def geometry_collection_bbox(test_dir):
    with open(os.path.join(test_dir, "data", "geometry-collection-bbox.json")) as f:
        return f.read()
