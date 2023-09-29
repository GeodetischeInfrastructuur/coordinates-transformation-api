from enum import Enum
from typing import Literal, Optional

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
    def nr_of_dimensions(self: "Crs") -> int:
        return len(self.axes)

    axes: list[Axis]

    def get_axis_label(self: "Crs") -> str:
        axes: list[Axis] = self.axes
        return ", ".join(list(map(lambda x: f"{x.abbrev} ({x.unit_name})", axes)))

    def get_x_unit_crs(self: "Crs") -> str:
        axe = next(
            (x for x in self.axes if x.abbrev.lower() in ["x", "e", "lon"]),
            None,
        )
        if axe is None:
            raise ValueError(
                f"unable to retrieve unit x axis (x, e, lon) CRS {self.crs_auth_identifier}"
            )
        unit_name = axe.unit_name
        if unit_name not in ["degree", "metre"]:
            raise ValueError(
                f"Unexpected unit in x axis (x, e, lon) CRS {self.crs_auth_identifier} - expected values: degree, meter, actual value: {unit_name}"
            )
        return unit_name


class Link(BaseModel):
    title: str
    type: str
    rel: str
    href: str


class LandingPage(BaseModel):
    title: str
    description: str
    links: list[Link]


class Conformance(BaseModel):
    conformsTo: list[str] = []  # noqa: N815


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

    def get_crs_auth_code(self: "CrsFeatureCollection") -> str | None:
        if self.crs is None:
            return None
        source_crs_urn_string = self.crs.properties.name
        source_crs_urn_list = source_crs_urn_string.split(":")
        crs_authority = source_crs_urn_list[4]
        crs_identifier = source_crs_urn_list[6]
        return f"{crs_authority}:{crs_identifier}"

    def set_crs_auth_code(self: "CrsFeatureCollection", crs_auth_code: str) -> None:
        crs_auth, crs_identifier = crs_auth_code.split(":")
        if self.crs is None:
            raise ValueError(f"self.crs is none of CrsFeatureCollection: {self}")
        self.crs.properties.name = f"urn:ogc:def:crs:{crs_auth}::{crs_identifier}"
