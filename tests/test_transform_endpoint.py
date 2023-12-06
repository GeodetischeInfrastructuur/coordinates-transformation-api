import pytest
from coordinate_transformation_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize(
    ("input", "expectation", "source_crs", "target_crs"),
    [
        (
            "10,10",
            {
                "type": "Point",
                "coordinates": [3.313687621, 47.974858156],
            },
            "EPSG:28992",
            "EPSG:4326",
        ),
        (
            "3.313687621,47.974858156",
            {
                "type": "Point",
                "coordinates": [9.9999, 10.0],
            },
            "EPSG:4326",
            "EPSG:28992",
        ),
    ],
)
def test_transform_get(input, expectation, source_crs, target_crs):
    response = client.get(
        f"/transform?coordinates={input}&source-crs={source_crs}&target-crs={target_crs}",
    )
    response_object = response.json()
    assert response.status_code == 200
    assert response_object == expectation
    api_version_headers_vals = response.headers.get_list("api-version")
    assert len(api_version_headers_vals) == 1
    assert api_version_headers_vals[0].startswith("2")


@pytest.mark.parametrize(
    ("input", "expectation", "source_crs", "target_crs"),
    [
        (
            {
                "type": "Point",
                "coordinates": [10, 10],
            },
            {
                "type": "Point",
                "coordinates": [3.313687621, 47.974858156],
            },
            "EPSG:28992",
            "EPSG:4326",
        ),
        (
            {
                "type": "Point",
                "coordinates": [3.313687621, 47.974858156],
            },
            {
                "type": "Point",
                "coordinates": [9.9999, 10.0],
            },
            "EPSG:4326",
            "EPSG:28992",
        ),
    ],
)
def test_transform_post(input, expectation, source_crs, target_crs):
    response = client.post(
        f"/transform?source-crs={source_crs}&target-crs={target_crs}",
        json=input,
    )
    response_object = response.json()
    assert response.status_code == 200
    assert response_object == expectation
    api_version_headers_vals = response.headers.get_list("api-version")
    assert len(api_version_headers_vals) == 1
    assert api_version_headers_vals[0].startswith("2")
