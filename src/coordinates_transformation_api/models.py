from enum import Enum
from typing import List, Literal, Optional

from geojson_pydantic import FeatureCollection
from pydantic import BaseModel, Field, computed_field


class Axis(BaseModel):
    name: str
    abbrev: str
    direction: str
    unit_conversion_factor: float
    unit_name: str
    unit_auth_code: str
    unit_code: str


class Crs(BaseModel):
    name: str
    type_name: str
    crs_auth_identifier: str

    authority: str
    identifier: str

    @computed_field  # type: ignore
    @property
    def nr_of_dimensions(self) -> int:
        return len(self.axes)

    axes: list[Axis]

    def get_axis_label(self) -> str:
        axes: list[Axis] = self.axes
        return ", ".join(list(map(lambda x: f"{x.abbrev} ({x.unit_name})", axes)))


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


class GeoJsonCrsProp(BaseModel):
    # OGC URN scheme - 8.2 in OGC 05-103
    # urn:ogc:def:crs:{crs_auth}:{crs_version}:{crs_identifier}
    name: str = Field(pattern=r"^urn:ogc:def:crs:.*?:.*?:.*?$")


class GeoJsonCrs(BaseModel):
    properties: GeoJsonCrsProp
    type: Literal["name"]


class CrsFeatureCollection(FeatureCollection):
    crs: Optional[GeoJsonCrs] = None

    def get_crs_auth_code(self) -> str | None:
        if self.crs is None:
            return None
        source_crs_urn_string = self.crs.properties.name
        source_crs_urn_list = source_crs_urn_string.split(":")
        crs_authority = source_crs_urn_list[4]
        crs_identifier = source_crs_urn_list[6]
        return f"{crs_authority}:{crs_identifier}"

    def set_crs_auth_code(self, crs_auth_code):
        crs_auth, crs_identifier = crs_auth_code.split(":")
        self.crs.properties.name = f"urn:ogc:def:crs:{crs_auth}::{crs_identifier}"
