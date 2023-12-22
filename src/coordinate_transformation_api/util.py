from __future__ import annotations

import logging
import math
import re
from collections.abc import Iterable
from importlib import resources as impresources
from importlib.metadata import version
from typing import Any, cast

import yaml
from fastapi import Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from geodense.geojson import CrsFeatureCollection
from geodense.lib import (  # type: ignore  # type: ignore
    THREE_DIMENSIONAL,
    GeojsonObject,
    _geom_type_check,
    apply_function_on_geojson_geometries,
    densify_geojson_object,
    flatten,
    get_density_check_fun,
)
from geodense.models import DenseConfig, GeodenseError
from geodense.types import Nested
from geojson_pydantic import Feature, GeometryCollection
from geojson_pydantic.geometries import Geometry
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from pyproj import CRS
from shapely import STRtree, box

from coordinate_transformation_api import assets
from coordinate_transformation_api.cityjson.models import CityjsonV113
from coordinate_transformation_api.constants import DENSIFY_CRS, DEVIATION_VALID_BBOX
from coordinate_transformation_api.crs_transform import (
    get_crs_transform_fun,
    get_json_coords_contains_inf_fun,
    get_precision,
    get_shapely_objects,
    get_transform_crs_fun,
    update_bbox_geojson_object,
)
from coordinate_transformation_api.models import (
    Crs as MyCrs,
)
from coordinate_transformation_api.models import (
    DataValidationError,
    DensifyError,
)
from coordinate_transformation_api.settings import app_settings
from coordinate_transformation_api.types import CoordinatesType

logger = logging.getLogger(__name__)


def validate_coords_source_crs(
    coordinates, source_crs, projections_axis_info: list[MyCrs]
):
    source_crs_dims = next(
        crs.nr_of_dimensions
        for crs in projections_axis_info
        if crs.crs_auth_identifier == source_crs
    )
    if source_crs_dims != len(coordinates.split(",")):
        raise_req_validation_error(
            "number of coordinates must match number of dimensions of source-crs",
            loc=("query", "coordinates"),
            input=source_crs,
        )


def camel_to_snake(s):
    return "".join(["_" + c.lower() if c.isupper() else c for c in s]).lstrip("_")


def extract_authority_code(crs: str) -> str:
    r = re.search(r"^(http://www\.opengis\.net/def/crs/)?(.[^/|:]*)(/.*/|:)(.*)", crs)
    if r is not None:
        return str(r[2] + ":" + r[4])

    return crs


def format_as_uri(crs: str) -> str:
    # NOTE: the /0/ is a placeholder and should be based on the epsg database version
    #   discuss what convention we want to follow here...
    return "http://www.opengis.net/def/crs/{}/0/{}".format(*crs.split(":"))


def get_source_crs_body(
    body: GeojsonObject | CityjsonV113,
) -> str | None:
    if isinstance(body, CrsFeatureCollection) and body.crs is not None:
        source_crs: str | None = body.get_crs_auth_code()
        if source_crs is None:
            return None
    elif isinstance(body, CrsFeatureCollection) and body.crs is None:
        return None
    elif (
        isinstance(body, CityjsonV113)
        and body.metadata is not None
        and body.metadata.referenceSystem is not None
    ):
        ref_system: str = body.metadata.referenceSystem
        crs_auth = ref_system.split("/")[-3]
        crs_id = ref_system.split("/")[-1]
        source_crs = f"{crs_auth}:{crs_id}"
    elif isinstance(body, CityjsonV113) and (
        body.metadata is None or body.metadata.referenceSystem is None
    ):
        return None
    else:
        return None
    return source_crs


def accept_html(request: Request) -> bool:
    if "accept" in request.headers:
        accept_header = request.headers["accept"]
        if "text/html" in accept_header:
            return True
    return False


def request_body_within_valid_bbox(body: GeojsonObject, source_crs: str) -> bool:
    if source_crs != DENSIFY_CRS:
        transform_f = get_transform_crs_fun(DENSIFY_CRS, source_crs)
        bbox = [
            *transform_f(DEVIATION_VALID_BBOX[:2]),
            *transform_f(DEVIATION_VALID_BBOX[2:]),
        ]
    coll = get_shapely_objects(body)
    tree = STRtree(coll)
    contains_index = tree.query(box(*bbox), predicate="contains").tolist()
    if len(coll) != len(contains_index):
        return False
    return True


def crs_transform(
    body: GeojsonObject,
    s_crs: str,
    t_crs: str,
    epoch: float | None = None,
) -> None:
    crs_transform_fun = get_crs_transform_fun(s_crs, t_crs, epoch)
    _ = apply_function_on_geojson_geometries(body, crs_transform_fun)
    if isinstance(body, CrsFeatureCollection):
        body.set_crs_auth_code(t_crs)
    update_bbox_geojson_object(body)


def density_check_request_body(
    body: GeojsonObject,
    source_crs: str,
    max_segment_deviation: float | None,
    max_segment_length: float | None,
) -> list[tuple[list[int], float]]:
    report: list[tuple[list[int], float]] = []

    _geom_type_check(body)

    if max_segment_deviation is not None:
        bbox_check_deviation_set(body, source_crs, max_segment_deviation)
        max_segment_length = convert_deviation_to_distance(max_segment_deviation)

    # TODO: @jochem add comments on langelijnen advies implementatie
    crs_transform(body, source_crs, DENSIFY_CRS)
    c = DenseConfig(CRS.from_authority(*DENSIFY_CRS.split(":")), max_segment_length)
    my_fun = get_density_check_fun(c)
    report = apply_function_on_geojson_geometries(body, my_fun)
    return report


def bbox_check_deviation_set(
    body: GeojsonObject, source_crs, max_segment_deviation
) -> None:
    if max_segment_deviation is not None and not request_body_within_valid_bbox(
        body, source_crs
    ):
        raise DataValidationError(
            f"GeoJSON geometries not within bounding box: {','.join([str(x) for x in DEVIATION_VALID_BBOX])}, use max_segment_length parameter instead of max_segment_deviation parameter. Use of max_segment_deviation parameter requires data to be within mentioned bounding box."
        )


def densify_request_body(
    body: GeojsonObject,
    source_crs: str,
    max_segment_deviation: float | None,
    max_segment_length: float | None,
) -> None:
    """transform coordinates of request body in place

    Args:
        body (Feature | FeatureCollection | _GeometryBase | GeometryCollection): request body to transform, will be transformed in place
        transformer (Transformer): pyproj Transformer object
    """

    if max_segment_deviation is not None:
        bbox_check_deviation_set(body, source_crs, max_segment_deviation)
        max_segment_length = convert_deviation_to_distance(max_segment_deviation)
    # TODO: @jochem add comments on langelijnen advies implementatie
    crs_transform(body, source_crs, DENSIFY_CRS)
    c = DenseConfig(CRS.from_authority(*DENSIFY_CRS.split(":")), max_segment_length)
    try:
        densify_geojson_object(body, c)
    except GeodenseError as e:
        raise DensifyError(str(e)) from e

    crs_transform(body, DENSIFY_CRS, source_crs)  # transform back


def init_oas() -> tuple[dict, str, str]:
    """initialize open api spec:
    - return projection info from oas
    - return app version
    - set api base url in api spec
    - set api version based on app version

    Returns:
        Tuple[dict, str, dict]: _description_
    """
    oas_filepath = impresources.files(assets) / "openapi.yaml"

    with oas_filepath.open("rb") as oas_file:
        oas = yaml.load(oas_file, yaml.SafeLoader)
        servers = [{"url": app_settings.base_url}]
        oas["servers"] = servers
        oas["info"]["version"] = version("coordinate_transformation_api")
    api_title = oas["info"]["title"]
    return (oas, api_title, oas["info"]["version"])


def convert_deviation_to_distance(a):
    d = math.sqrt(a / (24.15 * 10**-9))
    return d


def raise_response_validation_error(message: str, location):
    raise ResponseValidationError(
        errors=(
            ValidationError.from_exception_data(
                "ValueError",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "value-error",
                            message,
                        ),
                        loc=location,
                        input="",
                    ),
                ],
            )
        ).errors()
    )


def raise_request_validation_error(
    message: str,
    input: Any | None = None,
    loc: tuple[int | str, ...] | None = None,
    ctx: Any | None = None,
):
    raise RequestValidationError(
        errors=(
            ValidationError.from_exception_data(
                "ValueError",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "missing",
                            message,
                        ),
                        input=input,
                        **({"ctx": ctx} if ctx is not None else {}),  # type: ignore
                        **({"loc": loc} if loc is not None else {}),  # type: ignore
                    ),
                ],
            )
        ).errors(include_context=True)
    )


# TODO: remove duplicate method to raise error
def raise_req_validation_error(
    error_message,
    error_type="ValueError",
    input: Any | None = None,
    loc: tuple[int | str, ...] | None = None,
    ctx: Any | None = None,
):
    error_type_snake = camel_to_snake(error_type)
    raise RequestValidationError(
        errors=(
            ValidationError.from_exception_data(
                error_type,
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            error_type_snake,
                            error_message,
                        ),
                        input=input,
                        **({"ctx": ctx} if ctx is not None else {}),  # type: ignore
                        **({"loc": loc} if loc is not None else {}),  # type: ignore
                    )
                ],
            )
        ).errors()
    )


def convert_point_coords_to_wkt(coords):
    geom_type = "POINT"
    if len(coords) == THREE_DIMENSIONAL:
        geom_type = "POINT Z"
    return f"{geom_type}({' '.join([str(x) for x in coords])})"


def get_crs(crs_str: str, crs_list: list[MyCrs]) -> MyCrs:
    crs = next((x for x in crs_list if x.crs_auth_identifier == crs_str), None)
    if crs is None:
        raise ValueError(f"could not instantiate CRS object for CRS with id {crs_str}")

    return crs


def transform_coordinates(
    coordinates: Any, source_crs: str, target_crs: str, epoch, crs_list: list[MyCrs]
) -> Any:
    target_crs_crs = get_crs(
        target_crs,
        crs_list,
    )
    precision = get_precision(target_crs_crs)
    coordinate_list: CoordinatesType = list(
        float(x) for x in coordinates.split(",")
    )  # convert to list since we do not know dimensionality of coordinates
    transform_crs_fun = get_transform_crs_fun(
        source_crs, target_crs, precision=precision, epoch=epoch
    )
    transformed_coordinates = transform_crs_fun(coordinate_list)
    return transformed_coordinates


def validate_crs_transformed_geojson(body: GeojsonObject) -> None:
    validate_json_coords_fun = get_json_coords_contains_inf_fun()
    result: Nested[bool] = apply_function_on_geojson_geometries(
        body, validate_json_coords_fun
    )
    flat_result: Iterable[bool] = flatten(result)

    if any(flat_result):
        raise_response_validation_error(
            "Out of range float values are not JSON compliant", ["responseBody"]
        )


def get_source_crs(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection | CityjsonV113,
    source_crs: str,
    content_crs: str,
) -> str | None:
    crs_from_body = get_source_crs_body(body)
    s_crs = None
    if crs_from_body is not None:
        s_crs = crs_from_body
    elif crs_from_body is None and source_crs is not None:
        s_crs = source_crs
    elif crs_from_body is None and source_crs is None and content_crs is not None:
        s_crs = content_crs
    return s_crs


def post_transform_get_crss(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection | CityjsonV113,
    source_crs: str,
    target_crs: str,
    content_crs: str,
    accept_crs: str,
) -> tuple[str, str]:
    s_crs = get_source_crs(body, source_crs, content_crs)

    if s_crs is None and isinstance(body, CrsFeatureCollection):
        raise_request_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the provided object a query parameter source-crs or header content-crs",
            loc=[("body", "crs"), ("query", "source-crs"), ("header", "content-crs")],  # type: ignore
        )
    elif s_crs is None and isinstance(body, CityjsonV113):
        raise_request_validation_error(
            "metadata.referenceSystem field missing in CityJSON request body",
            loc=[
                (
                    "body",
                    "metadata.referenceSystem",
                ),
                ("query", "source-crs"),
                (
                    "header",
                    "content-crs",
                ),
            ],  # type: ignore
        )
    elif s_crs is None:
        raise_request_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the query parameter source-crs or header content-crs",
            loc=("query", "source-crs", "header", "content-crs"),
        )

    if target_crs is not None:
        t_crs = target_crs
    elif target_crs is None and accept_crs is not None:
        t_crs = accept_crs
    else:
        raise_request_validation_error(
            "No target CRS found in request. Defining a target CRS is required through the query parameter target-crs or header accept-crs",
            loc=("query", "target-crs", "header", "accept-crs"),
        )

    s_crs_str = cast(str, s_crs)
    s_crs = extract_authority_code(s_crs_str)
    t_crs = extract_authority_code(t_crs)

    return s_crs, t_crs


def get_transform_get_crss(
    source_crs: str,
    target_crs: str,
    content_crs: str,
    accept_crs: str,
) -> tuple[str, str]:
    if source_crs is not None:
        s_crs = source_crs
    elif source_crs is None and content_crs is not None:
        s_crs = content_crs
    else:
        raise_request_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the query parameter source-crs or header content-crs",
            loc=("query", "source-crs", "header", "content-crs"),
        )

    if target_crs is not None:
        t_crs = target_crs
    elif target_crs is None and accept_crs is not None:
        t_crs = accept_crs
    else:
        raise_request_validation_error(
            "No target CRS found in request. Defining a target CRS is required through the query parameter target-crs or header accept-crs",
            loc=("query", "target-crs", "header", "accept-crs"),
        )

    s_crs = extract_authority_code(s_crs)
    t_crs = extract_authority_code(t_crs)

    return s_crs, t_crs


def get_src_crs_densify(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection,
    source_crs: str,
    content_crs: str,
) -> str:
    s_crs = get_source_crs(body, source_crs, content_crs)
    if s_crs is None and isinstance(body, CrsFeatureCollection):
        raise_request_validation_error(
            "No source CRS found in request. Defining a source CRS is required in the FeatureCollection request body, the source-crs query parameter or the content-crs header",
            loc=("body", "crs", "query", "source-crs", "header", "content-crs"),
        )
    elif s_crs is None:
        raise_request_validation_error(
            "No source CRS found in request. Defining a source CRS is required through the query parameter source-crs or header content-crs",
            loc=("query", "source-crs", "header", "content-crs"),
        )
    return cast(str, s_crs)


def set_response_headers(
    *args, headers: dict[str, str] | None = None
) -> dict[str, str]:
    headers = {} if headers is None else headers
    for arg in args:
        key, val = arg
        headers[key] = str(val)
    return headers
    # headers = {"content-crs": format_as_uri(t_crs)}
    # if epoch:
    #     headers["epoch"] = str(epoch)

    # return headers
