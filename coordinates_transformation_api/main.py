import json
import os
from importlib import resources as impresources
from typing import List

import uvicorn
import yaml
from fastapi import FastAPI, Query, Request, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from coordinates_transformation_api.fastapi_rfc7807 import middleware

from . import assets

API_TITLE = "Coordinates Transformation API"

OAS_FILEPATH = impresources.files(assets) / "openapi.yaml"
with OAS_FILEPATH.open("rb") as oas_file:
    OPEN_API_SPEC = yaml.load(oas_file, yaml.SafeLoader)
API_VERSION = OPEN_API_SPEC["info"]["version"]
BASE_DIR = os.path.dirname(__file__)

app = FastAPI(docs_url=None)  #
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
    source_crs: str = Query(alias="source-crs"),
    target_crs: str = Query(alias="target-crs"),
    coordinates: str = Query(alias="coordinates"),
):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinates},
        "properties": {"sourcecrs": source_crs, "targetcrs": target_crs},
    }


@app.post("/transform")
async def transform(sourcec_rs: str, target_crs: str):
    return [
        {
            "data": "string",
            "properties": {"sourcecrs": sourcec_rs, "targetcrs": target_crs},
        }
    ]


def get_oas():
    return OPEN_API_SPEC


app.openapi = get_oas


def main():
    # TODO: add CLI args for uvicorn, see https://www.uvicorn.org/settings/
    uvicorn.run(
        "coordinates_transformation_api.main:app", workers=2, port=8000, host="0.0.0.0"
    )


if __name__ == "__main__":
    main()
