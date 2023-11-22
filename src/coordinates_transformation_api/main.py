import json
import logging
import os
from importlib import resources as impresources
from typing import Callable, Union, cast

import uvicorn
from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from geodense.geojson import CrsFeatureCollection
from geojson_pydantic import Feature
from geojson_pydantic.geometries import Geometry, GeometryCollection

from coordinates_transformation_api import assets
from coordinates_transformation_api.cityjson.models import CityjsonV113
from coordinates_transformation_api.fastapi_rfc7807 import middleware
from coordinates_transformation_api.limit_middleware.middleware import (
    ContentSizeLimitMiddleware,
    TimeoutMiddleware,
)
from coordinates_transformation_api.models import (
    Conformance,
    Crs,
    DensityCheckReport,
    LandingPage,
    Link,
    TransformGetAcceptHeaders,
)
from coordinates_transformation_api.settings import app_settings
from coordinates_transformation_api.util import (
    accept_html,
    convert_point_coords_to_wkt,
    crs_transform,
    densify_request_body,
    density_check_request_body,
    extract_authority_code,
    format_as_uri,
    get_source_crs_body,
    init_oas,
    raise_response_validation_error,
    raise_validation_error,
    transform_coordinates,
    validate_coords_source_crs,
    validate_crs_transformed_geojson,
    validate_crss,
    validate_input_max_segment_deviation_length,
)

assets_resources = impresources.files(assets)
logging_conf = assets_resources.joinpath("logging.conf")


logging.config.fileConfig(str(logging_conf), disable_existing_loggers=False)
logger = logging.getLogger(__name__)
logger.setLevel(app_settings.log_level)
if not app_settings.debug:  # suppres pyproj warnings in prod
    logging.getLogger("pyproj").setLevel(logging.ERROR)


OPEN_API_SPEC: dict
API_VERSION: str
CRS_LIST: list[Crs]
OPEN_API_SPEC, API_TITLE, API_VERSION = init_oas()
crs_identifiers = OPEN_API_SPEC["components"]["schemas"]["crs-enum"]["enum"]
CRS_LIST = [Crs.from_crs_str(x) for x in crs_identifiers]
BASE_DIR: str = os.path.dirname(__file__)


app: FastAPI = FastAPI(docs_url=None)
# note: order of adding middleware is required for it to work
middleware.register(app)
app.add_middleware(
    ContentSizeLimitMiddleware, max_content_size=app_settings.max_size_request_body
)
app.add_middleware(TimeoutMiddleware, timeout_seconds=app_settings.request_timeout)

if app_settings.cors_allow_origins:
    allow_origins: list[str]
    if app_settings.cors_allow_origins == "*":
        allow_origins = [app_settings.cors_allow_origins]
    else:
        allow_origins = [str(x).rstrip("/") for x in app_settings.cors_allow_origins]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.mount(
    "/static",
    StaticFiles(directory=f"{BASE_DIR}/assets/static"),
    name="static",
)


@app.middleware("http")
async def add_api_version(request: Request, call_next: Callable) -> Response:
    response_body = {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Not Found",
    }
    response = Response(
        content=json.dumps(response_body),
        status_code=404,
        media_type="application/problem+json",
    )

    if request.url.path != "/" and request.url.path.endswith("/"):
        # overwrite response in case route is a know route with trailing slash
        for route in app.routes:
            if isinstance(route, APIRoute) and request.url.path == f"{route.path}/":
                response_body[
                    "detail"
                ] = f"not found, path contains trailing slash try {route.path}"
                response = Response(
                    content=json.dumps(response_body),
                    status_code=404,
                    media_type="application/problem+json",
                )
    else:
        response = await call_next(request)
    response.headers["API-Version"] = API_VERSION
    return response


@app.get("/openapi", include_in_schema=False)
@app.get("/openapi.html", include_in_schema=False)
async def openapi(
    request: Request, format: str = Query(alias="f", default=None)
) -> Response:
    if format == "html" or (
        accept_html(request) and format != "json"
    ):  # return html when format=html, return json when format=json, but return html when accept header accepts html
        return get_swagger_ui_html(
            openapi_url="./openapi.json",
            title=f"{API_TITLE} - Swagger UI",
            swagger_favicon_url="https://www.nsgi.nl/o/iv-kadaster-business-theme/images/favicon.ico",
        )
    else:  # by default return JSON
        return JSONResponse(
            content=app.openapi(),
            status_code=200,
            media_type="application/json",
        )


@app.get("/", response_model=LandingPage)
async def landingpage():  # type: ignore  # noqa: ANN201
    self = Link(
        title="API Landing Page",
        rel="self",
        href=f"{app_settings.base_url.rstrip('/')}/?f=json",
        type="application/json",
    )

    oas = Link(
        title="Open API Specification as JSON",
        rel="service-desc",
        href=f"{app_settings.base_url.rstrip('/')}/openapi?f=json",
        type="application/openapi+json",
    )

    oas_html = Link(
        title="Open API Specification as HTML",
        rel="service-desc",
        href=f"{app_settings.base_url.rstrip('/')}/openapi?f=html",
        type="text/html",
    )

    conformance = Link(
        title="Conformance Declaration as JSON",
        rel="http://www.opengis.net/def/rel/ogc/1.0/conformance",
        href=f"{app_settings.base_url.rstrip('/')}/conformance",
        type="application/json",
    )
    return LandingPage(
        title=API_TITLE,
        description="Landing page describing the capabilities of this service",
        links=[self, oas, oas_html, conformance],
    )


@app.get("/crss", response_model=list[Crs])
async def crss() -> list[Crs]:
    return CRS_LIST


@app.get("/crss/{crs_id}", response_model=Crs)
async def crs(crs_id: str) -> Crs | Response:
    gen = (crs for crs in CRS_LIST if crs.crs_auth_identifier == crs_id)
    result = next(gen, None)

    if result is None:
        return Response(
            content=json.dumps(
                {
                    "type": "unknown-crs",
                    "title": "Crs Not Found",
                    "status": 404,
                    "detail": crs_id,
                }
            ),
            status_code=404,
            media_type="application/problem+json",
        )
    return result


@app.get("/conformance", response_model=Conformance)
async def conformance() -> Conformance:
    return Conformance(
        conformsTo=[
            "https://docs.ogc.org/is/19-072/19-072.html",
            "https://gitdocumentatie.logius.nl/publicatie/api/adr/",
        ]
    )


@app.get("/transform")
async def transform(  # noqa: PLR0913, ANN201
    coordinates: str = Query(
        alias="coordinates", regex=r"^(\d+\.?\d*),(\d+\.?\d*)(,\d+\.?\d*)?$"
    ),
    source_crs: str = Query(alias="source-crs", default=None),
    target_crs: str = Query(alias="target-crs", default=None),
    epoch: float = Query(alias="epoch", default=None),
    content_crs: str = Header(alias="content-crs", default=None),
    accept_crs: str = Header(alias="accept-crs", default=None),
    accept: str = Header(default=TransformGetAcceptHeaders.json),
):
    if source_crs is not None:
        s_crs = source_crs
    elif source_crs is None and content_crs is not None:
        s_crs = content_crs
    else:
        raise_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the query parameter source-crs or header content-crs",
            ("query", "source-crs", "header", "content-crs"),
        )

    if target_crs is not None:
        t_crs = target_crs
    elif target_crs is None and accept_crs is not None:
        t_crs = accept_crs
    else:
        raise_validation_error(
            "No target CRS found in request. Defining a target CRS is required through the query parameter target-crs or header accept-crs",
            ("query", "target-crs", "header", "accept-crs"),
        )

    s_crs = extract_authority_code(s_crs)
    t_crs = extract_authority_code(t_crs)

    validate_crss(s_crs, t_crs, CRS_LIST)
    validate_coords_source_crs(coordinates, s_crs, CRS_LIST)

    target_crs_crs = next(
        (x for x in CRS_LIST if x.crs_auth_identifier == target_crs), None
    )
    if target_crs_crs is None:
        raise ValueError(
            f"could not instantiate CRS object for CRS with id {target_crs}"
        )
    transformed_coordinates = transform_coordinates(
        coordinates, source_crs, target_crs, epoch, target_crs_crs
    )

    if float("inf") in [abs(x) for x in transformed_coordinates]:
        raise_response_validation_error(
            "Out of range float values are not JSON compliant", ["responseBody"]
        )

    if accept == str(TransformGetAcceptHeaders.wkt.value):
        wkt_string = convert_point_coords_to_wkt(coordinates)
        PlainTextResponse(
            wkt_string,
            headers=set_response_headers(t_crs, epoch),
        )
    else:  # default case serve json
        return JSONResponse(
            content={"type": "Point", "coordinates": transformed_coordinates},
            headers=set_response_headers(t_crs, epoch),
        )


@app.post(
    "/densify",
    response_model=Union[Feature, CrsFeatureCollection, Geometry],
    response_model_exclude_none=True,
)
async def densify(  # noqa: ANN201
    body: Union[Feature, CrsFeatureCollection, Geometry, GeometryCollection],
    source_crs: str = Query(alias="source-crs", default=None),
    content_crs: str = Header(alias="content-crs", default=None),
    max_segment_deviation: float = Query(
        alias="max-segment-deviation", default=None, ge=0.0001
    ),
    max_segment_length: float = Query(alias="max-segment-length", default=None, ge=200),
):
    validate_input_max_segment_deviation_length(
        max_segment_deviation, max_segment_length
    )

    s_crs = get_source_crs(body, source_crs, content_crs)
    if s_crs is None and isinstance(body, CrsFeatureCollection):
        raise_validation_error(
            "No source CRS found in request. Defining a source CRS is required in the FeatureCollection request body, the source-crs query parameter or the content-crs header",
            ("body", "crs", "query", "source-crs", "header", "content-crs"),
        )
    elif s_crs is None:
        raise_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the query parameter source-crs or header content-crs",
            ("query", "source-crs", "header", "content-crs"),
        )
    s_crs_str = cast(str, s_crs)
    densify_request_body(body, s_crs_str, max_segment_deviation, max_segment_length)
    return JSONResponse(
        content=body.model_dump(exclude_none=True),
        headers=set_response_headers(s_crs_str),
    )


def get_source_crs(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection | CityjsonV113,
    source_crs: str,
    content_crs: str,
) -> str | None:
    crs_from_body = get_source_crs_body(body)
    s_crs = None
    if crs_from_body is not None:
        s_crs = crs_from_body
    elif crs_from_body is None and source_crs is not None:
        s_crs = source_crs
    elif crs_from_body is None and source_crs is None and content_crs is not None:
        s_crs = content_crs
    return s_crs


def set_response_headers(t_crs: str, epoch: float | None = None) -> dict[str, str]:
    headers = {"content-crs": format_as_uri(t_crs)}
    if epoch:
        headers["epoch"] = str(epoch)

    return headers


@app.post(
    "/density-check",
    response_model=DensityCheckReport,
    response_model_exclude_none=True,
)
async def density_check(  # noqa: ANN201
    body: Union[Feature, CrsFeatureCollection, Geometry, GeometryCollection],
    source_crs: str = Query(alias="source-crs", default=None),
    content_crs: str = Header(alias="content-crs", default=None),
    max_segment_deviation: float = Query(
        alias="max-segment-deviation", default=None, ge=0.0001
    ),
    max_segment_length: float = Query(alias="max-segment-length", default=200, ge=200),
):
    validate_input_max_segment_deviation_length(
        max_segment_deviation, max_segment_length
    )

    s_crs = get_source_crs(body, source_crs, content_crs)

    if s_crs is None and isinstance(body, CrsFeatureCollection):
        raise_validation_error(
            "No source CRS found in request. Defining a source CRS is required in the FeatureCollection request body, the source-crs query parameter or the content-crs header",
            ("body", "crs", "query", "source-crs", "header", "content-crs"),
        )
    elif s_crs is None:
        raise_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the query parameter source-crs or header content-crs",
            ("query", "source-crs", "header", "content-crs"),
        )
    s_crs_str = cast(str, s_crs)
    report = density_check_request_body(
        body, s_crs_str, max_segment_deviation, max_segment_length
    )
    result = DensityCheckReport(passes_check=not len(report) > 0, report=report)
    return result


@app.post(
    "/transform",
    response_model=Union[
        Feature, CrsFeatureCollection, Geometry, GeometryCollection, CityjsonV113
    ],
    response_model_exclude_none=True,
)
async def post_transform(  # noqa: ANN201, PLR0913
    body: Union[
        Feature, CrsFeatureCollection, Geometry, GeometryCollection, CityjsonV113
    ],
    source_crs: str = Query(alias="source-crs", default=None),
    target_crs: str = Query(alias="target-crs", default=None),
    epoch: float = Query(alias="epoch", default=None),
    content_crs: str = Header(alias="content-crs", default=None),
    accept_crs: str = Header(alias="accept-crs", default=None),
):
    s_crs = get_source_crs(body, source_crs, content_crs)

    if s_crs is None and isinstance(body, CrsFeatureCollection):
        raise_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the provided object a query parameter source-crs or header content-crs",
            ("body", "crs", "query", "source-crs", "header", "content-crs"),
        )
    elif s_crs is None and isinstance(body, CityjsonV113):
        raise_validation_error(
            "metadata.referenceSystem field missing in CityJSON request body",
            (
                "body",
                "metadata.referenceSystem",
                "query",
                "source-crs",
                "header",
                "content-crs",
            ),
        )
    elif s_crs is None:
        raise_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the query parameter source-crs or header content-crs",
            ("query", "source-crs", "header", "content-crs"),
        )

    if target_crs is not None:
        t_crs = target_crs
    elif target_crs is None and accept_crs is not None:
        t_crs = accept_crs
    else:
        raise_validation_error(
            "No target CRS found in request. Defining a target CRS is required through the query parameter target-crs or header accept-crs",
            ("query", "target-crs", "header", "accept-crs"),
        )

    s_crs_str = cast(str, s_crs)
    s_crs = extract_authority_code(s_crs_str)
    t_crs = extract_authority_code(t_crs)

    validate_crss(s_crs, t_crs, CRS_LIST)

    if isinstance(body, CityjsonV113):
        body.crs_transform(s_crs, t_crs, epoch)
        return Response(
            content=body.model_dump_json(exclude_none=True),
            media_type="application/city+json",
        )
    else:
        crs_transform(body, s_crs, t_crs, epoch)
        validate_crs_transformed_geojson(body)

        return JSONResponse(
            content=body.model_dump(exclude_none=True),
            headers=set_response_headers(t_crs, epoch),
        )


app.openapi = lambda: OPEN_API_SPEC  # type: ignore


def main() -> None:
    uvicorn.run(
        "coordinates_transformation_api.main:app",
        workers=2,
        port=8000,
        host="0.0.0.0",  # noqa: S104
    )


if __name__ == "__main__":
    main()
