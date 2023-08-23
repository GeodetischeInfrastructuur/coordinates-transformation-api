import json
import logging
import os
from importlib import resources as impresources
from typing import Union

import uvicorn
from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from geojson_pydantic import Feature
from geojson_pydantic.geometries import Geometry, GeometryCollection

from coordinates_transformation_api import assets
from coordinates_transformation_api.fastapi_rfc7807 import middleware
from coordinates_transformation_api.limit_middleware.middleware import (
    ContentSizeLimitMiddleware, TimeoutMiddleware)
from coordinates_transformation_api.models import (Conformance, Crs,
                                                   CrsFeatureCollection,
                                                   LandingPage, Link,
                                                   TransformGetAcceptHeaders)
from coordinates_transformation_api.settings import app_settings
from coordinates_transformation_api.util import (get_source_crs_body,
                                                 get_transform_callback,
                                                 get_transformer, init_oas,
                                                 transform_request_body,
                                                 traverse_geojson_coordinates,
                                                 validate_coords_source_crs,
                                                 validate_crss)

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


@app.get("/", response_model=LandingPage)
async def landingpage():
    self = Link(
        title="This document as JSON",
        rel="self",
        href="http://localhost:8000/?f=json",
        type="application/json",
    )

    return LandingPage(
        title="Coordinatetransformation API",
        description="Landing page describing what the capabilities are of this service",
        links=[self],
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
    coordinates: str = Query(alias="coordinates"),
    accept: str = Header(default=TransformGetAcceptHeaders.json),
    content_crs: str = Header(alias="content-crs", default=None),
    accept_crs: str = Header(alias="accept-crs", default=None),
):
    if source_crs is None and content_crs != None:
        source_crs = content_crs

    if target_crs is None and accept_crs != None:
        target_crs = accept_crs

    validate_crss(source_crs, target_crs, CRS_LIST)
    validate_coords_source_crs(coordinates, source_crs, CRS_LIST)

    transformer = get_transformer(source_crs, target_crs)

    coordinates_list: list = [float(x) for x in coordinates.split(",")]

    transformed_coordinates = traverse_geojson_coordinates(
        coordinates_list, callback=get_transform_callback(transformer)
    )

    if accept == str(TransformGetAcceptHeaders.wkt.value):
        if len(transformed_coordinates) == 3:
            return PlainTextResponse(
                f"POINT Z ({' '.join([str(x) for x in transformed_coordinates])})",
                headers={"content-crs": target_crs},
            )

        return PlainTextResponse(
            f"POINT({' '.join([str(x) for x in transformed_coordinates])})",
            headers={"content-crs": target_crs},
        )
    else:  # default case serve json
        return JSONResponse(
            content={"type": "Point", "coordinates": transformed_coordinates},
            headers={"content-crs": target_crs},
        )


@app.post("/transform")  # type: ignore
async def transform(
    body: Union[Feature, CrsFeatureCollection, Geometry, GeometryCollection],
    source_crs: str = Query(alias="source-crs", default=None),
    target_crs: str = Query(alias="target-crs", default=None),
    content_crs: str = Header(alias="content-crs", default=None),
    accept_crs: str = Header(alias="accept-crs", default=None),
):
    if source_crs is None and content_crs != None:
        source_crs = content_crs

    if target_crs is None and accept_crs != None:
        target_crs = accept_crs

    if source_crs is None:
        source_crs = get_source_crs_body(body)
    validate_crss(source_crs, target_crs, CRS_LIST)
    transformer = get_transformer(source_crs, target_crs)
    transform_request_body(body, transformer)
    return body


app.openapi = lambda: OPEN_API_SPEC  # type: ignore


def main():
    uvicorn.run(
        "coordinates_transformation_api.main:app", workers=2, port=8000, host="0.0.0.0"
    )


if __name__ == "__main__":
    main()
