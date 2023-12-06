from __future__ import annotations

import logging
import math
import re
from collections.abc import Iterable
from importlib import resources as impresources
from importlib.metadata import version
from typing import Any

import yaml
from fastapi import Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from geodense.geojson import CrsFeatureCollection
from geodense.lib import (  # type: ignore  # type: ignore
    THREE_DIMENSIONAL,
    GeojsonObject,
    apply_function_on_geojson_geometries,
    densify_geojson_object,
    flatten,
    get_density_check_fun,
)
from geodense.models import (
    DenseConfig,
)
from geodense.types import Nested
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
from coordinate_transformation_api.models import Crs as MyCrs
from coordinate_transformation_api.settings import app_settings
from coordinate_transformation_api.types import CoordinatesType

logger = logging.getLogger(__name__)


def validate_crs_transformation(
    source_crs, target_crs, projections_axis_info: list[MyCrs]
):
    source_crs_dims = next(
        crs.nr_of_dimensions
        for crs in projections_axis_info
        if crs.crs_auth_identifier == source_crs
    )
    target_crs_dims = next(
        crs.nr_of_dimensions
        for crs in projections_axis_info
        if crs.crs_auth_identifier == target_crs
    )

    if source_crs_dims < target_crs_dims:
        raise_req_validation_error(
            f"number of dimensions of target-crs should be equal or less then that of the source-crs\n * source-crs: {source_crs}, dimensions: {source_crs_dims}\n * target-crs {target_crs}, dimensions: {target_crs_dims}",
            loc=("query", "target-crs"),
            input=(source_crs, target_crs),
        )


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


def validate_input_max_segment_deviation_length(deviation, length):
    if length is None and deviation is None:
        raise_req_validation_error(
            "max_segment_length or max_segment_deviation should be set",
            loc=("query", "max_segment_length|max_segment_deviation"),
            input=[None, None],
        )


def validate_input_crs(value, name, projections_axis_info: list[MyCrs]):
    if not any(
        crs for crs in projections_axis_info if crs.crs_auth_identifier == value
    ):
        raise_req_validation_error(
            f"{name} should be one of {', '.join([str(x.crs_auth_identifier) for x in projections_axis_info])}",
            loc=("query", name),
            input=value,
        )


def extract_authority_code(crs: str) -> str:
    r = re.search("^(http://www.opengis.net/def/crs/)?(.[^/|:]*)(/.*/|:)(.*)", crs)
    if r is not None:
        return str(r[2] + ":" + r[4])

    return crs


def format_as_uri(crs: str) -> str:
    # NOTE: the /0/ is a placeholder and should be based on the epsg database version
    #   discuss what convention we want to follow here...
    return "http://www.opengis.net/def/crs/{}/0/{}".format(*crs.split(":"))


def validate_crss(source_crs: str, target_crs: str, projections_axis_info):
    validate_input_crs(source_crs, "source-crs", projections_axis_info)
    validate_input_crs(target_crs, "target_crs", projections_axis_info)
    validate_crs_transformation(source_crs, target_crs, projections_axis_info)


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
    max_segment_deviation: float,
    max_segment_length: float,
) -> list[tuple[list[int], float]]:
    report: list[tuple[list[int], float]] = []

    # TODO: add tests to check behaviour when points are supplied
    validate_input_max_segment_deviation_length(
        max_segment_deviation, max_segment_length
    )
    bbox_check_deviation_set(body, source_crs, max_segment_deviation)
    if max_segment_deviation is not None:
        max_segment_length = convert_deviation_to_distance(max_segment_deviation)

    crs_transform(body, source_crs, DENSIFY_CRS)

    # density check
    c = DenseConfig(CRS.from_authority(*DENSIFY_CRS.split(":")), max_segment_length)
    my_fun = get_density_check_fun(c)
    report = apply_function_on_geojson_geometries(body, my_fun)
    return report


def bbox_check_deviation_set(
    body: GeojsonObject, source_crs, max_segment_deviation
) -> None:
    if max_segment_deviation is None and not request_body_within_valid_bbox(
        body, source_crs
    ):
        # request body not within valid bbox todo density check
        # TODO: raise error
        print("body not inside bbox")


def densify_request_body(
    body: GeojsonObject,
    source_crs: str,
    max_segment_deviation: float,
    max_segment_length: float,
) -> None:
    """transform coordinates of request body in place

    Args:
        body (Feature | FeatureCollection | _GeometryBase | GeometryCollection): request body to transform, will be transformed in place
        transformer (Transformer): pyproj Transformer object
    """
    validate_input_max_segment_deviation_length(
        max_segment_deviation, max_segment_length
    )
    bbox_check_deviation_set(body, source_crs, max_segment_deviation)
    if max_segment_deviation is not None:
        max_segment_length = convert_deviation_to_distance(max_segment_deviation)
    # TODO: add comments on langelijnen advies implementatie
    crs_transform(body, source_crs, DENSIFY_CRS)
    c = DenseConfig(CRS.from_authority(*DENSIFY_CRS.split(":")), max_segment_length)
    densify_geojson_object(body, c)
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


def convert_distance_to_deviation(d):
    a = 24.15 * 10**-9 * d**2
    return a


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


def raise_validation_error(message: str, location):
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
                        loc=location,
                        input="",
                    ),
                ],
            )
        ).errors()
    )


def raise_req_validation_error(
    error_message, error_type="ValueError", input=any, loc: tuple[int | str, ...] = ()
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
                        loc=loc,
                        input=input,
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


def transform_coordinates(
    coordinates: Any, source_crs: str, target_crs: str, epoch, target_crs_crs
) -> Any:
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
