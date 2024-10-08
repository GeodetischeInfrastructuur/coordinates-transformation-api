from __future__ import annotations

import logging
import math
import re
from functools import partial
from importlib import resources as impresources
from importlib.metadata import version
from typing import Any, cast

import yaml
from fastapi import Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from geodense.geojson import CrsFeatureCollection
from geodense.lib import (  # type: ignore
    GeojsonObject,
    check_density_geojson_object,
    densify_geojson_object,
    transform_geojson_geometries,
    traverse_geojson_geometries,
    validate_geom_type,
)
from geodense.models import DenseConfig, GeodenseError
from geojson_pydantic import Feature, GeometryCollection
from geojson_pydantic.geometries import Geometry
from geojson_pydantic.types import Position
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from pyproj import CRS
from shapely import STRtree, box

from coordinate_transformation_api import assets
from coordinate_transformation_api.cityjson.models import CityjsonV113
from coordinate_transformation_api.constants import (
    DENSIFY_CRS_2D,
    DENSIFY_CRS_3D,
    DEVIATION_VALID_BBOX,
    THREE_DIMENSIONAL,
)
from coordinate_transformation_api.crs_transform import (
    get_bbox_from_coordinates,
    get_coordinate_from_geometry,
    get_precision,
    get_transform_crs_fun,
    mutate_geom_coordinates,
)
from coordinate_transformation_api.models import (
    Crs as AvailableCrs,
)
from coordinate_transformation_api.models import (
    DensifyError,
    DeviationOutOfBboxError,
)
from coordinate_transformation_api.settings import app_settings

BBOX_3D_DIMENSION = 6

logger = logging.getLogger(__name__)


def validate_coords_source_crs(position: Position, source_crs, projections_axis_info: list[AvailableCrs]):
    source_crs_dims = next(
        crs.nr_of_dimensions for crs in projections_axis_info if source_crs == crs.crs_auth_identifier
    )
    if source_crs_dims != len(position):
        raise_request_validation_error(
            "number of coordinates must match number of dimensions of source-crs",
            loc=("query", "coordinates"),
            input=source_crs,
        )


def camel_to_snake(s):
    return "".join(["_" + c.lower() if c.isupper() else c for c in s]).lstrip("_")


def extract_authority_code(crs: str) -> tuple[str, str]:
    r = re.search(r"^(https?://www\.opengis\.net/def/crs/)?(.[^/|:]*)(/.*/|:)(.*)", crs)
    if r is not None:
        auth = r[2]
        code = r[4]
        return auth, code
    else:
        split = crs.split(":")
        if len(split) != 2:  # noqa: PLR2004
            raise ValueError("expected crs string format is: {auth}:{code}")
        auth, code = split
        return auth, code


def format_as_uri(crs: str) -> str:
    # NOTE: the /0/ is a placeholder and should be based on the epsg database version
    #   discuss what convention we want to follow here...
    return "http://www.opengis.net/def/crs/{}/0/{}".format(*crs.split(":"))


def get_source_crs_body(
    body: GeojsonObject | CityjsonV113,
) -> str | None:
    source_crs: str | None = None
    if isinstance(body, CrsFeatureCollection) and body.crs is not None:
        source_crs = body.get_crs_auth_code()
    elif isinstance(body, CityjsonV113) and body.metadata is not None and body.metadata.referenceSystem is not None:
        ref_system: str = body.metadata.referenceSystem
        crs_auth = ref_system.split("/")[-3]
        crs_id = ref_system.split("/")[-1]
        source_crs = f"{crs_auth}:{crs_id}"
    return source_crs


def accept_html(request: Request) -> bool:
    if "accept" in request.headers:
        accept_header = request.headers["accept"]
        if "text/html" in accept_header:
            return True
    return False


def request_body_within_valid_bbox(body: GeojsonObject, source_crs: str) -> bool:
    if source_crs not in [DENSIFY_CRS_2D, DENSIFY_CRS_3D]:
        transform_f = get_transform_crs_fun(str_to_crs(source_crs), str_to_crs(DENSIFY_CRS_2D))

        if body.bbox is None:
            # set bbox to initial value, otherwise wont be updated
            body.bbox = (0, 0, 0, 0)
            body_t = traverse_geojson_geometries(body, None, update_bbox)

        body_bbox = body_t.bbox

        if len(body_t.bbox) == BBOX_3D_DIMENSION:
            # reduce bbox to 2D
            body_bbox = body_t.bbox[0:2] + body_t.bbox[3:5]

        body_bbox_t = [
            *transform_f(body_bbox[:2]),
            *transform_f(body_bbox[2:]),
        ]

    shapely_bbox = [box(*body_bbox_t)]
    tree = STRtree(shapely_bbox)
    contains_index = tree.query(box(*DEVIATION_VALID_BBOX), predicate="contains").tolist()  # type: ignore
    return len(shapely_bbox) == len(contains_index)


def update_bbox(item: GeojsonObject):
    if item.bbox is not None:  # only update bbox if already set
        coords = transform_geojson_geometries(item, get_coordinate_from_geometry)
        bbox = None
        # TODO: collect bboxes if not geometry object instead of coordinates
        if coords:
            coords = list(filter(lambda x: x is not None, coords))
            bbox = get_bbox_from_coordinates(coords)
        item.bbox = bbox


def crs_transform(
    body: GeojsonObject,
    s_crs: CRS,
    t_crs: CRS,
    epoch: float | None = None,
) -> GeojsonObject:
    t_callback = get_transform_crs_fun(s_crs, t_crs, epoch=epoch)
    crs_transform_fun = partial(mutate_geom_coordinates, t_callback)
    body_t = traverse_geojson_geometries(body, crs_transform_fun, update_bbox)

    if isinstance(body_t, CrsFeatureCollection):
        body_t.set_crs_auth_code("{}:{}".format(*t_crs.to_authority()))
    return body_t


def density_check_request_body(
    body: GeojsonObject,
    source_crs: CRS,
    max_segment_deviation: float | None,
    max_segment_length: float | None,
    epoch: float | None,
) -> CrsFeatureCollection:
    """Run density check with geodense implementation, by running density check in DENSIFY_CRS."""
    validate_geom_type(body)
    if max_segment_deviation is not None:
        bbox_check_deviation_set(body, source_crs, max_segment_deviation)
        max_segment_length = convert_deviation_to_distance(max_segment_deviation)

    transform_crs = (
        str_to_crs(DENSIFY_CRS_3D) if len(source_crs.axis_info) == THREE_DIMENSIONAL else str_to_crs(DENSIFY_CRS_2D)
    )
    transform = "{}:{}".format(*source_crs.to_authority()) not in [
        DENSIFY_CRS_3D,
        DENSIFY_CRS_2D,
    ]

    if transform:
        body_t = crs_transform(
            body, source_crs, transform_crs, epoch=epoch
        )  # !NOTE: crs_transform is required for density_check and densify
    c = DenseConfig(CRS.from_authority(*DENSIFY_CRS_2D.split(":")), max_segment_length)
    failed_line_segments = check_density_geojson_object(c, body_t)

    if transform:
        failed_line_segments_t = crs_transform(failed_line_segments, transform_crs, source_crs, epoch=epoch)
    return failed_line_segments_t


def bbox_check_deviation_set(body: GeojsonObject, source_crs, max_segment_deviation) -> None:
    if max_segment_deviation is not None and not request_body_within_valid_bbox(body, source_crs):
        raise DeviationOutOfBboxError(
            f"Geometries not within bounding box: {DEVIATION_VALID_BBOX!s}. Use of max_segment_deviation parameter requires data to be within mentioned bounding box."
        )


def densify_request_body(
    body: GeojsonObject,
    source_crs: str,
    max_segment_deviation: float | None,
    max_segment_length: float | None,
) -> GeojsonObject:
    """densify request body according to geodense by densifying in DENSIFY_CRS

    Args:
        body (Feature | FeatureCollection | _GeometryBase | GeometryCollection): request body to transform, will be transformed in place
        transformer (Transformer): pyproj Transformer object
    """

    if max_segment_deviation is not None:
        bbox_check_deviation_set(body, source_crs, max_segment_deviation)
        max_segment_length = convert_deviation_to_distance(max_segment_deviation)

    source_crs_crs = CRS.from_authority(*source_crs.split(":"))
    transform_crs = DENSIFY_CRS_3D if len(source_crs_crs.axis_info) == THREE_DIMENSIONAL else DENSIFY_CRS_2D
    transform = source_crs not in [DENSIFY_CRS_3D, DENSIFY_CRS_2D]

    s_crs = str_to_crs(source_crs)
    t_crs = str_to_crs(transform_crs)

    body_t = body
    if transform:
        body_t = crs_transform(body, s_crs, t_crs)
    c = DenseConfig(CRS.from_authority(*transform_crs.split(":")), max_segment_length)
    try:
        body_t_d = densify_geojson_object(c, body_t)
    except GeodenseError as e:
        raise DensifyError(str(e)) from e

    body_d = body_t_d
    if transform:
        body_d = crs_transform(body_t_d, t_crs, s_crs)  # transform back to source_crs
    return body_d


def init_oas(crs_config) -> tuple[dict, str, str]:
    """initialize open api spec:
    - return projection info from oas
    - return app version
    - set api base url in api spec
    - set api version based on app version

    Returns:
        Tuple[dict, str, dict]: _description_
    """
    oas_filepath = impresources.files(assets) / "openapi.yaml"

    available_crss = list(crs_config.keys())
    available_crss_uri = list(map(lambda x: x["uri"], list(crs_config.values())))

    with oas_filepath.open("rb") as oas_file:
        oas = yaml.load(oas_file, yaml.SafeLoader)
        servers = [{"url": app_settings.base_url.strip("/")}]
        oas["servers"] = servers
        oas["info"]["version"] = version("coordinate_transformation_api")
        oas["components"]["schemas"]["CrsEnum"]["enum"] = available_crss
        oas["components"]["schemas"]["CrsHeaderEnum"]["enum"] = available_crss_uri

        if app_settings.api_key_in_oas:
            api_key_header_def = {
                "APIKeyHeader": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "apikey",
                }
            }
            security: dict = {"security": [{"APIKeyHeader": []}]}
            if app_settings.example_api_key is not None:
                api_key_description = f"\n\nThe Demo API key is `{app_settings.example_api_key}` and is intended for exploratory use of the API only. This key may stop working without warning."
                oas["info"]["description"] = oas["info"]["description"] + api_key_description

            oas["components"]["securitySchemes"] = api_key_header_def

            for path in oas["paths"]:
                if path != "/openapi":
                    for op in oas["paths"][path]:
                        oas["paths"][path][op] = oas["paths"][path][op] | security

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


def convert_point_coords_to_wkt(coords):
    geom_type = "POINT"
    if len(coords) == THREE_DIMENSIONAL:
        geom_type = "POINT Z"
    return f"{geom_type}({' '.join([str(x) for x in coords])})"


def check_crs_is_known(crs_str: str, crs_list: list[AvailableCrs]) -> None:
    crs = next((x for x in crs_list if x.crs_auth_identifier == crs_str), None)
    if crs is None:
        raise ValueError(f"could not instantiate CRS object for CRS with id {crs_str}")


def transform_coordinates(coordinates: Position, source_crs: CRS, target_crs: CRS, epoch) -> Any:
    precision = get_precision(target_crs)

    transform_crs_fun = get_transform_crs_fun(source_crs, target_crs, precision=precision, epoch=epoch)
    transformed_coordinates = transform_crs_fun(coordinates)
    return transformed_coordinates


def get_source_crs(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection | CityjsonV113,
    source_crs: str,
    content_crs: str,
) -> str | None:
    crs_from_body = get_source_crs_body(body)

    if crs_from_body is not None:
        return crs_from_body
    elif crs_from_body is None and source_crs is not None:
        return source_crs
    elif crs_from_body is None and source_crs is None and content_crs is not None:
        return content_crs

    return None


def post_transform_get_crss(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection | CityjsonV113,
    source_crs: str,
    target_crs: str,
    content_crs: str,
    accept_crs: str,
) -> tuple[CRS, CRS]:
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
    s_authority_code = extract_authority_code(s_crs_str)
    t_authority_code = extract_authority_code(t_crs)

    return CRS.from_authority(*s_authority_code), CRS.from_authority(*t_authority_code)


def get_transform_get_crss(
    source_crs: str,
    target_crs: str,
    content_crs: str,
    accept_crs: str,
) -> tuple[CRS, CRS]:
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

    s_authority_code = extract_authority_code(s_crs)
    t_authority_code = extract_authority_code(t_crs)

    return CRS.from_authority(*s_authority_code), CRS.from_authority(*t_authority_code)


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


def set_response_headers(*args, headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = {} if headers is None else headers
    for arg in args:
        key, val = arg
        headers[key] = str(val)
    return headers


def str_to_crs(crs_str: str) -> CRS:
    return CRS.from_authority(*crs_str.split(":"))
