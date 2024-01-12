import pytest
from coordinate_transformation_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize(
    ("input", "expectation", "source_crs", "target_crs"),
    [
        (
            "128410.0958,445806.4960",
            {
                "type": "Point",
                "coordinates": [52.0, 5.0],
            },
            "EPSG:28992",
            "EPSG:4326",
        ),
        (
            "52.0,5.0",
            {
                "type": "Point",
                "coordinates": [128410.0958, 445806.4960],
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
    assert response.status_code == 200  # noqa: PLR2004
    assert response_object == expectation
    api_version_headers_vals = response.headers.get_list("api-version")
    assert len(api_version_headers_vals) == 1
    assert api_version_headers_vals[0].startswith("2")


@pytest.mark.parametrize(
    ("request_body", "expectation", "source_crs", "target_crs"),
    [
        (
            {
                "type": "Point",
                "coordinates": [10, 10],
            },
            {
                "type": "Point",
                "coordinates": [47.974858137, 3.313687707],
            },
            "EPSG:28992",
            "EPSG:4326",
        ),
        (
            {
                "type": "Point",
                "coordinates": [47.974858137, 3.313687707],
            },
            {
                "type": "Point",
                "coordinates": [10, 10],
            },
            "EPSG:4326",
            "EPSG:28992",
        ),
    ],
)
def test_transform_post(request_body, expectation, source_crs, target_crs):
    response = client.post(
        f"/transform?source-crs={source_crs}&target-crs={target_crs}",
        json=request_body,
    )
    response_object = response.json()
    assert response.status_code == 200  # noqa: PLR2004
    assert response_object == expectation
    api_version_headers_vals = response.headers.get_list("api-version")
    assert len(api_version_headers_vals) == 1
    assert api_version_headers_vals[0].startswith("2")


@pytest.mark.parametrize(
    ("source_crs", "target_crs", "content_crs", "expectation"),
    [
        ("EPSG:99999", "EPSG:28992", None, [["query", "source-crs"]]),
        (
            "EPSG:99999",
            "EPSG:99999",
            None,
            [["query", "target-crs"], ["query", "source-crs"]],
        ),
        (
            "EPSG:99999",
            "EPSG:99999",
            "EPSG:99999",
            [
                ["query", "target-crs"],
                ["query", "source-crs"],
                ["header", "content-crs"],
            ],
        ),
    ],
)
def test_transform_post_invalid_crs_returns_400(
    source_crs, target_crs, content_crs, expectation
):
    request_body = {
        "type": "Point",
        "coordinates": [9.9999, 10.0],
    }
    headers = None
    if content_crs is not None:
        headers = {"content-crs": content_crs}
    response = client.post(
        f"/transform?source-crs={source_crs}&target-crs={target_crs}",
        json=request_body,
        headers=headers,
    )
    assert response.status_code == 400  # noqa: PLR2004
    response_body = response.json()
    error_locs = [x["loc"] for x in response_body["errors"]]

    assert len(error_locs) == len(expectation)
    for item in expectation:
        assert item in error_locs


def test_transform_post_no_crs_returns_error():
    request_body = {
        "type": "FeatureCollection",
        "name": "punten",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Point",
                    "coordinates": [9.9999, 10.0],
                },
            }
        ],
    }
    response = client.post("/transform", json=request_body)
    assert response.status_code == 400  # noqa: PLR2004
    response_body = response.json()
    assert response_body["errors"][0]["msg"].startswith(
        "No source CRS found in request"
    )


@pytest.mark.parametrize(
    ("source_crs", "target_crs", "content_crs", "expectation"),
    [
        ("EPSG:99999", "EPSG:28992", None, [["query", "source-crs"]]),
        (
            "EPSG:99999",
            "EPSG:99999",
            None,
            [["query", "target-crs"], ["query", "source-crs"]],
        ),
        (
            "EPSG:99999",
            "EPSG:99999",
            "EPSG:99999",
            [
                ["query", "target-crs"],
                ["query", "source-crs"],
                ["header", "content-crs"],
            ],
        ),
    ],
)
def test_transform_get_invalid_crs_returns_400(
    source_crs, target_crs, content_crs, expectation
):
    headers = None
    if content_crs is not None:
        headers = {"content-crs": content_crs}
    response = client.get(
        f"/transform?source-crs={source_crs}&target-crs={target_crs}&coordinates=3.313687621,47.974858156",
        headers=headers,
    )
    assert response.status_code == 400  # noqa: PLR2004
    response_body = response.json()
    error_locs = [x["loc"] for x in response_body["errors"]]

    assert len(error_locs) == len(expectation)
    for item in expectation:
        assert item in error_locs
