import pytest
from coordinate_transformation_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize(
    ("input", "expectation", "source_crs", "target_crs", "epoch"),
    [
        (
            "128410.0958,445806.4960",
            {
                "type": "Point",
                "coordinates": [5.0, 52.0],
            },
            "EPSG:28992",
            "EPSG:4326",
            None,
        ),
        (
            "5.0,52.0",
            {
                "type": "Point",
                "coordinates": [128410.0958, 445806.4960],
            },
            "EPSG:4326",
            "EPSG:28992",
            None,
        ),
        (
            "5.0,52.0,43",
            {
                "type": "Point",
                "coordinates": [128410.0958, 445806.4960, -0.4754],
            },
            "EPSG:7931",
            "EPSG:7415",
            None,
        ),
        (
            "2.0,2.0,43",
            {
                "type": "Point",
                "coordinates": [-303977.8041, -5471504.9711],
            },
            "EPSG:7931",
            "EPSG:7415",
            None,
        ),
        (
            "2.0,2.0,43",
            {
                "type": "Point",
                "coordinates": [-303977.8041, -5471504.9711],
            },
            "EPSG:7931",
            "EPSG:28992",
            None,
        ),
        (
            "78835.84,457831.732,9.724",
            {
                "type": "Point",
                "coordinates": [
                    3914987.764,
                    292686.6764,
                    5009926.0544,
                ],  # [3914987.7917, 292686.6338, 5009926.0202],
            },
            "EPSG:7415",
            "EPSG:7789",
            "2012.5",
        ),
        (
            "78835.84,457831.732,9.724",
            {
                "type": "Point",
                "coordinates": [
                    4.275510904,
                    52.103483244,
                    53.134,
                ],  # [4.275510253, 52.103482881, 53.122],
            },
            "EPSG:7415",
            "EPSG:7912",
            "2012.5",
        ),
    ],
)
def test_transform_get(input, expectation, source_crs, target_crs, epoch):
    if epoch is not None:
        response = client.get(
            f"/transform?coordinates={input}&source-crs={source_crs}&target-crs={target_crs}&epoch={epoch}",
        )
    else:
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
                "coordinates": [3.313687707, 47.974858137],
            },
            "EPSG:28992",
            "EPSG:4326",
        ),
        (
            {
                "type": "Point",
                "coordinates": [3.313687707, 47.974858137],
            },
            {
                "type": "Point",
                "coordinates": [10, 10],
            },
            "EPSG:4326",
            "EPSG:28992",
        ),
        # NOTE: feature[1] has dropped height after transformation
        (
            {
                "type": "FeatureCollection",
                "crs": {
                    "properties": {"name": "urn:ogc:def:crs:EPSG::7931"},
                    "type": "name",
                },
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [5, 52, 43]},
                        "properties": {"prop0": "value0"},
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [2, 2, 43]},
                        "properties": {"prop0": "value0"},
                    },
                ],
            },
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [128410.0958, 445806.4960, -0.4754],
                        },
                        "properties": {"prop0": "value0"},
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [-303977.8041, -5471504.9711],
                        },
                        "properties": {"prop0": "value0"},
                    },
                ],
                "crs": {
                    "properties": {"name": "urn:ogc:def:crs:EPSG::7415"},
                    "type": "name",
                },
            },
            "EPSG:7931",
            "EPSG:7415",
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


@pytest.mark.parametrize(
    ("request_body", "expectation", "source_crs", "target_crs"),
    [
        (
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-87853.9838, 228817.8356],
                        [318159.6959, 894090.7466],
                    ],
                },
                "properties": {"id": "1"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[2.0, 50.0], [8.0, 55.999999996]],
                },
                "properties": {"id": "1"},
            },
            "EPSG:28992",
            "EPSG:9067",
        ),
    ],
)
def test_transform_densify_check_post(
    request_body, expectation, source_crs, target_crs
):
    response = client.post(
        f"/transform?source-crs={source_crs}&target-crs={target_crs}&density-check=true&max-segment-length=10000000",
        json=request_body,
    )
    response_object = response.json()
    assert response.status_code == 200  # noqa: PLR2004
    assert response_object == expectation
    api_version_headers_vals = response.headers.get_list("api-version")
    assert len(api_version_headers_vals) == 1
    assert api_version_headers_vals[0].startswith("2")
