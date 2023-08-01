from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import yaml
import uvicorn

default_headers = {"API-Version": "2.0.1"}

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


def start():
    uvicorn.run("coordinates_transformation_api.main:app", workers=2, host="0.0.0.0", port=8000, reload=True)
