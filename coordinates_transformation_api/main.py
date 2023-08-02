from importlib import resources as impresources
from typing import List
import time

import uvicorn
import yaml
from fastapi import FastAPI, Request
from pydantic import BaseModel

from . import assets

app = FastAPI(docs_url="/api")


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
    response = await call_next(request)
    response.headers["API-Version"] = API_VERSION
    return response


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


@app.get("/transformation")
async def transformation():
    return [
        {
            "data": "string",
        }
    ]


@app.get("/transform")
async def transform(sourcecrs: str, targetcrs: str, coordinates: str):
    coordinates = list(map(float, coordinates.split(",")))

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinates},
        "properties": {"sourcecrs": sourcecrs, "targetcrs": targetcrs},
    }


@app.post("/transform")
async def transform():
    return [
        {
            "data": "string",
        }
    ]


OAS_FILEPATH = impresources.files(assets) / "openapi.yaml"

with OAS_FILEPATH.open("rb") as oas_file:
    OPEN_API_SPEC = yaml.load(oas_file, yaml.SafeLoader)
API_VERSION = OPEN_API_SPEC["info"]["version"]
app.openapi = OPEN_API_SPEC


def start():
    uvicorn.run(
        "coordinates_transformation_api.main:app",
        workers=2,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
