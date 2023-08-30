import json
import logging
import os
from importlib import resources as impresources
from typing import Union

import uvicorn
from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from geojson_pydantic import Feature, FeatureCollection
from geojson_pydantic.geometries import Geometry, GeometryCollection
from pyproj import CRS, network

from coordinates_transformation_api import assets
from coordinates_transformation_api.callback import get_transform_callback
from coordinates_transformation_api.cityjson.models import CityjsonV113
from coordinates_transformation_api.fastapi_rfc7807 import middleware
from coordinates_transformation_api.limit_middleware.middleware import (
    ContentSizeLimitMiddleware,
    TimeoutMiddleware,
)
from coordinates_transformation_api.models import (
    Conformance,
    Crs,
    CrsFeatureCollection,
    TransformGetAcceptHeaders,
)
from coordinates_transformation_api.settings import app_settings
from coordinates_transformation_api.util import (
    accept_html,
    extract_authority_code,
    format_as_uri,
    get_precision,
    get_source_crs_body,
    init_oas,
    raise_validation_error,
    transform_request_body,
    validate_coords_source_crs,
    validate_crss,
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
OPEN_API_SPEC, API_TITLE, API_VERSION, CRS_LIST = init_oas()
BASE_DIR: str = os.path.dirname(__file__)

network.set_network_enabled(True)  # TODO: remove before commit

app: FastAPI = FastAPI(docs_url=None)
# note: order of adding middleware is required for it to work
middleware.register(app)
app.add_middleware(
    ContentSizeLimitMiddleware, max_content_size=app_settings.max_size_request_body
)
app.add_middleware(TimeoutMiddleware, timeout_seconds=app_settings.request_timeout)


app.mount(
    "/static",
    StaticFiles(directory=f"{BASE_DIR}/assets/static"),
    name="static",
)

@app.middleware("http")
async def add_api_version(request: Request, call_next):
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
            if isinstance(route, APIRoute):
                if request.url.path == f"{route.path}/":
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
async def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{API_TITLE} - Swagger UI",
        swagger_favicon_url="https://www.nsgi.nl/o/iv-kadaster-business-theme/images/favicon.ico",
    )


@app.get("/")
async def landingpage(request: Request, format: str = Query(alias="f", default=None)):

    if format == "html" or (accept_html(request) and format != "json"): # return html when format=html, return json when format=json, but return html when accept header accepts html
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{API_TITLE} - Swagger UI",
            swagger_favicon_url="https://www.nsgi.nl/o/iv-kadaster-business-theme/images/favicon.ico",
        )
    else: # by default return JSON
        return JSONResponse(
                        content=app.openapi(),
                        status_code=200,
                        media_type="application/json",
                    )


@app.get("/crss", response_model=list[Crs])
async def crss():
    return CRS_LIST


@app.get("/crss/{crs_id}", response_model=Crs)
async def crs(crs_id: str):
    gen = (crs for crs in CRS_LIST if crs.crs_auth_identifier == crs_id)
    result = next(gen, None)

    if result == None:
        # TODO: return not found 404

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
async def conformance():
    return Conformance(conformsTo={"mekker", "blaat"})


@app.get("/transform")
async def transform(
    source_crs: str = Query(alias="source-crs", default=None),
    target_crs: str = Query(alias="target-crs", default=None),
    coordinates: str = Query(
        alias="coordinates", regex=r"^(\d+\.?\d*),(\d+\.?\d*)(,\d+\.?\d*)?$"
    ),
    accept: str = Header(default=TransformGetAcceptHeaders.json),
    content_crs: str = Header(alias="content-crs", default=None),
    accept_crs: str = Header(alias="accept-crs", default=None),
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
    precision = get_precision(target_crs_crs)

    coordinates_list: tuple[float, ...] = tuple(
        float(x) for x in coordinates.split(",")
    )
    callback = get_transform_callback(source_crs, target_crs, precision=precision)
    transformed_coordinates = callback(coordinates_list)

    if accept == str(TransformGetAcceptHeaders.wkt.value):
        if len(transformed_coordinates) == 3:
            return PlainTextResponse(
                f"POINT Z ({' '.join([str(x) for x in transformed_coordinates])})",
                headers={"content-crs": format_as_uri(t_crs)},
            )

        return PlainTextResponse(
            f"POINT({' '.join([str(x) for x in transformed_coordinates])})",
            headers={"content-crs": format_as_uri(t_crs)},
        )
    else:  # default case serve json
        return JSONResponse(
            content={"type": "Point", "coordinates": transformed_coordinates},
            headers={"content-crs": format_as_uri(t_crs)},
        )


@app.post("/transform", response_model=Union[Feature, CrsFeatureCollection, Geometry, GeometryCollection, CityjsonV113], response_model_exclude_none=True)  # type: ignore
async def transform(
    body: Union[
        Feature, CrsFeatureCollection, Geometry, GeometryCollection, CityjsonV113
    ],
    source_crs: str = Query(alias="source-crs", default=None),
    target_crs: str = Query(alias="target-crs", default=None),
    content_crs: str = Header(alias="content-crs", default=None),
    accept_crs: str = Header(alias="accept-crs", default=None),
):
    crs_from_body = get_source_crs_body(body)

    if crs_from_body is not None:
        s_crs = crs_from_body
    elif crs_from_body is None and source_crs is not None:
        s_crs = source_crs
    elif crs_from_body is None and source_crs is None and content_crs is not None:
        s_crs = content_crs
    else:
        if isinstance(body, CrsFeatureCollection):
            raise_validation_error(
                "No source CRS found in request. Defining a source CRS is required through the provided object a query parameter source-crs or header content-crs",
                ("body", "crs", "query", "source-crs", "header", "content-crs"),
            )
        elif isinstance(body, CityjsonV113):
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

    if isinstance(body, CityjsonV113):
        body.crs_transform(s_crs, t_crs)
        return Response(
            content=body.model_dump_json(exclude_none=True),
            media_type="application/city+json",
        )
    else:
        transform_request_body(body, s_crs, t_crs, CRS_LIST)
        return JSONResponse(
            content=body.model_dump(exclude_none=True),
            headers={"content-crs": format_as_uri(t_crs)},
        )


app.openapi = lambda: OPEN_API_SPEC  # type: ignore


def main():
    uvicorn.run(
        "coordinates_transformation_api.main:app", workers=2, port=8000, host="0.0.0.0"
    )


if __name__ == "__main__":
    main()
