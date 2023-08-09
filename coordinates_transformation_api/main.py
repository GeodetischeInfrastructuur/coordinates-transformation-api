import json
import os
from enum import Enum
from importlib import resources as impresources
from typing import Iterable, List, Tuple, Union

import uvicorn
import yaml
from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from geojson_pydantic import Feature, FeatureCollection
from geojson_pydantic.geometries import (Geometry, GeometryCollection,
                                         _GeometryBase)
from pydantic import BaseModel, ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from pyproj import CRS, Transformer

from coordinates_transformation_api import assets
from coordinates_transformation_api.fastapi_rfc7807 import middleware
from coordinates_transformation_api.util import (get_projs_axis_info,
                                                 transform_geom)


def init_oas() -> Tuple[dict, str, dict]:
    oas_filepath = impresources.files(assets) / "openapi.yaml"

    with oas_filepath.open("rb") as oas_file:
        oas = yaml.load(oas_file, yaml.SafeLoader)
        crs_identifiers = oas["components"]["schemas"]["crs"]["enum"]
        projs_axis_info = get_projs_axis_info(crs_identifiers)
        crs_param_description = ""
        for key in projs_axis_info.keys():
            crs_param_description += f"* `{key}`: format: `{', '.join(projs_axis_info[key]['axis_labels'])}`, dimensions: {projs_axis_info[key]['dimensions']}\n"  # ,
        oas["components"]["parameters"]["source-crs"][
            "description"
        ] = f"Source Coordinate Reference System\n{crs_param_description}"
        oas["components"]["parameters"]["target-crs"][
            "description"
        ] = f"Target Coordinate Reference System\n{crs_param_description}"
    api_version = oas["info"]["version"]
    return (oas, api_version, projs_axis_info)


API_TITLE: str = "Coordinates Transformation API"
OPEN_API_SPEC: dict = {}
API_VERSION: str = ""
PROJS_AXIS_INFO: dict = {}
OPEN_API_SPEC, API_VERSION, PROJS_AXIS_INFO = init_oas()

BASE_DIR: str = os.path.dirname(__file__)

app: FastAPI = FastAPI(docs_url=None)
middleware.register(app)


app.mount(
    "/static",
    StaticFiles(directory=f"{BASE_DIR}/assets/static"),
    name="static",
)


class Link(BaseModel):
    title: str
    type: str
    rel: str
    href: str


class LandingPage(BaseModel):
    title: str
    description: str
    links: List[Link]


class Conformance(BaseModel):
    conformsTo: List[str] = []


class TransformGetAcceptHeaders(Enum):
    json = "application/json"
    wkt = "text/plain"


def validate_crs_transformation(source_crs, target_crs):
    source_crs_dims = PROJS_AXIS_INFO[source_crs]["dimensions"]
    target_crs_dims = PROJS_AXIS_INFO[target_crs]["dimensions"]

    if source_crs_dims < target_crs_dims:
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                f"number of dimensions of target-crs should be equal or less then that of the source-crs\n * source-crs: {source_crs}, dimensions: {source_crs_dims}\n * target-crs {target_crs}, dimensions: {target_crs_dims}",
                            ),
                            loc=("query", "target-crs"),
                        )
                    ],
                )
            ).errors()
        )


def validate_coords_source_crs(coordinates, source_crs):
    source_crs_dims = PROJS_AXIS_INFO[source_crs]["dimensions"]
    if source_crs_dims != len(coordinates.split(",")):
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                "number of coordinates must match number of dimensions of source-crs",
                            ),
                            loc=("query", "coordinates"),
                        )
                    ],
                )
            ).errors()
        )


def validate_input_crs(value, name):
    if value not in PROJS_AXIS_INFO.keys():
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                f"{name} should be one of {', '.join(PROJS_AXIS_INFO.keys())}",
                            ),
                            loc=("query", name),
                        )
                    ],
                )
            ).errors()
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


@app.get("/conformance", response_model=Conformance)
async def conformance():
    return Conformance(conformsTo={"mekker", "blaat"})


@app.get("/transform")
async def transform(
    response: Response,
    source_crs: str = Query(alias="source-crs"),
    target_crs: str = Query(alias="target-crs"),
    coordinates: str = Query(alias="coordinates"),
    accept: str = Header(default=TransformGetAcceptHeaders.json),
):
    validate_input_crs(source_crs, "source-crs")
    validate_input_crs(target_crs, "target_crs")
    validate_crs_transformation(source_crs, target_crs)
    validate_coords_source_crs(coordinates, source_crs)

    coordinates_list: list = coordinates.split(",")
    source_crs_crs = CRS.from_authority(*source_crs.split(":"))
    target_crs_crs = CRS.from_authority(*target_crs.split(":"))
    transformer = Transformer.from_crs(source_crs_crs, target_crs_crs)
    transformed_coordinates = transformer.transform(*coordinates_list)

    if accept == str(TransformGetAcceptHeaders.wkt.value):
        return PlainTextResponse(
            f"POINT({' '.join([str(x) for x in transformed_coordinates])})"
        )
    else:  # default case serve json
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": transformed_coordinates},
        }


@app.post("/transform")  # type: ignore
async def transform(
    body: Union[Feature, FeatureCollection, Geometry, GeometryCollection],
    source_crs: str = Query(alias="source-crs"),
    target_crs: str = Query(alias="target-crs"),
):
    validate_input_crs(source_crs, "source-crs")
    validate_input_crs(target_crs, "target_crs")
    validate_crs_transformation(source_crs, target_crs)
    source_crs_crs = CRS.from_authority(*source_crs.split(":"))
    target_crs_crs = CRS.from_authority(*target_crs.split(":"))
    transformer = Transformer.from_crs(source_crs_crs, target_crs_crs)

    if isinstance(body, Feature):
        feature_body: Feature = body
        geom: Geometry = feature_body.geometry
        transform_geom(transformer, geom)
    elif isinstance(body, FeatureCollection):
        fc_body: FeatureCollection = body
        features: Iterable[Feature] = fc_body.features
        for feature in features:
            feature.geometry = transform_geom(transformer, feature.geometry)
    elif isinstance(body, _GeometryBase):
        geom: Geometry = body
        transform_geom(transformer, geom)
    elif isinstance(body, GeometryCollection):
        geometries: Iterable[Geometry] = body
        for geometry in geometries:
            geometry = transform_geom(transformer, geometry)
    return body


def get_oas() -> dict:
    return OPEN_API_SPEC


app.openapi = get_oas  # type: ignore


def main():
    # TODO: add CLI args for uvicorn, see https://www.uvicorn.org/settings/
    uvicorn.run(
        "coordinates_transformation_api.main:app", workers=2, port=8000, host="0.0.0.0"
    )


if __name__ == "__main__":
    main()
