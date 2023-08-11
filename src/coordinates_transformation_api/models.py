from enum import Enum
from typing import List

from pydantic import BaseModel


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
