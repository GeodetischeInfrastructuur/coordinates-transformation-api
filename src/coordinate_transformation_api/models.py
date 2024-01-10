from enum import Enum

from geodense.geojson import CrsFeatureCollection
from pydantic import BaseModel, Field, computed_field
from pyproj import CRS as ProjCrs  # noqa: N811


class DataValidationError(Exception):
    type_str = "nsgi.nl/data-validation-error"
    title = "Data Validation Error"
    pass


class NotFoundError(Exception):
    type_str = "nsgi.nl/not-found-error"
    title = "Not Found Error"
    pass


class CrsNotFoundError(NotFoundError):
    type_str = "nsgi.nl/crs-not-found-error"
    title = "CRS Not Found Error"

    def __init__(
        self: "CrsNotFoundError",
        crs_id: str,
    ) -> None:
        # Call the base class constructor with the parameters it needs
        super().__init__(f"CRS with id {crs_id} not supported by API")
        # Now for your custom code...
        self.crs_id = crs_id


class TransformationNotPossibleError(DataValidationError):
    type_str = "nsgi.nl/transformation-not-possible"
    title = "Transformation Not Possible"

    def __init__(
        self: "TransformationNotPossibleError",
        src_crs: str,
        target_crs: str,
        reason: str = "no transformation path available",
    ) -> None:
        # Call the base class constructor with the parameters it needs
        message = (
            f"Transformation not possible between {src_crs} and {target_crs}, {reason}"
        )
        super().__init__(message)
        # Now for your custom code...


class DensityCheckFailedError(DataValidationError):
    type_str = "nsgi.nl/density-check-failed"
    title = "Density Check Failed"

    def __init__(
        self: "DensityCheckFailedError",
        message: str,
        report: list[tuple[list[int], float]],
    ) -> None:
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        # Now for your custom code...
        self.report = report


class DeviationOutOfBboxError(DataValidationError):
    type_str = "nsgi.nl/deviation-data-outside-bbox"
    title = "Data Outside Bounding Box when Using Deviation"
    pass


class DensityCheckError(DataValidationError):
    type_str = "nsgi.nl/density-check-error"
    title = "Error Occured In Density Check"
    pass


class DensifyError(DataValidationError):
    type_str = "nsgi.nl/densification-error"
    title = "Error Occured in Densification"
    pass


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


class DensityCheckReport(BaseModel):
    check_result: bool = Field(..., alias="checkResult")
    failed_line_segments: CrsFeatureCollection | None = Field(
        ..., alias="failedLineSegments"
    )

    @classmethod
    def from_fc_report(
        cls, fc_report: CrsFeatureCollection  # noqa: ANN102
    ) -> "DensityCheckReport":
        check_result = len(fc_report.features) == 0
        return DensityCheckReport(
            checkResult=check_result,
            failedLineSegments=None if check_result else fc_report,
        )


class TransformGetAcceptHeaders(Enum):
    json = "application/json"
    wkt = "text/plain"


class DensityCheckResult(Enum):
    not_run = "not-run"
    success = "success"
    failed = "failed"
    not_applicable_geom_type = "not-applicable-geom-type"
    not_implemented = "not-implemented"


class Axis(BaseModel):
    name: str
    abbrev: str
    direction: str
    unit_conversion_factor: float
    unit_name: str
    unit_auth_code: str
    unit_code: str


class Crs(BaseModel):
    crs: str
    name: str
    type_name: str
    crs_auth_identifier: str
    authority: str
    identifier: str

    @classmethod
    def from_crs_str(cls, crs_st: str) -> "Crs":  # noqa: ANN102
        # Do some math here and later set the values
        auth, identifier = crs_st.split(":")
        crs = ProjCrs.from_authority(auth, identifier)
        axes = [
            Axis(
                name=a.name,
                abbrev=a.abbrev,
                direction=a.direction,
                unit_conversion_factor=a.unit_conversion_factor,
                unit_name=a.unit_name,
                unit_auth_code=a.unit_auth_code,
                unit_code=a.unit_code,
            )
            for a in crs.axis_info
        ]
        return cls(
            crs=f"https://www.opengis.net/def/crs/{auth}/0/{identifier}",
            name=crs.name,
            type_name=crs.type_name,
            crs_auth_identifier=crs.srs,
            axes=axes,
            authority=auth,
            identifier=identifier,
        )

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
