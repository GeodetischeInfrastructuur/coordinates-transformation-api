from fastapi import FastAPI, Response
from pydantic import BaseModel
from starlette.responses import RedirectResponse, JSONResponse
from typing import List

import yaml
import json

default_headers = {"API-Version": "2.0.0"}

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


# class VndResponse(JSONResponse):
#     media_type = 'application/vnd.oai.openapi+json;version=3.0'


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


def custom_openapi():
    with open("openapi.yaml", "rb") as openapi:
        return yaml.load(openapi, yaml.SafeLoader)


app.openapi = custom_openapi
