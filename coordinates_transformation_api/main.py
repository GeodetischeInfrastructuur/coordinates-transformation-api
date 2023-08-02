from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List
import yaml
import uvicorn

from importlib import resources as impresources
from . import assets

app = FastAPI(docs_url="/openapi")

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
async def transform(source_crs: str = Query(alias="source-crs"), target_crs: str = Query(alias="target-crs"), coordinates: str = Query(alias="coordinates")):

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

def custom_openapi():
    oas_file_resource = (impresources.files(assets) / "openapi.yaml")
    with oas_file_resource.open("rb") as oas_file:
        return yaml.load(oas_file, yaml.SafeLoader)


app.openapi = custom_openapi

def start():
    uvicorn.run("coordinates_transformation_api.main:app", workers=2, host="0.0.0.0", port=8000, reload=True)
