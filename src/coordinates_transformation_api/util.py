from __future__ import annotations

import logging
import math
import re
from collections import Counter
from collections.abc import Iterable
from importlib import resources as impresources
from itertools import chain
from typing import Any, Callable, TypedDict, cast

import yaml
from fastapi import Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from geodense.lib import (  # type: ignore
    check_density_geometry_coordinates,
    densify_geometry_coordinates,
)
from geodense.models import (
    DenseConfig,
)
from geojson_pydantic import (
    Feature,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from geojson_pydantic.geometries import Geometry, GeometryCollection, _GeometryBase
from geojson_pydantic.types import (
    BBox,
    LineStringCoords,
    MultiLineStringCoords,
    MultiPointCoords,
    MultiPolygonCoords,
    PolygonCoords,
    Position,
)
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from pyproj import CRS
from shapely import GeometryCollection as ShpGeometryCollection
from shapely import STRtree, box
from shapely.geometry import shape

from coordinates_transformation_api import assets
from coordinates_transformation_api.callback import (
    get_transform_callback,
)
from coordinates_transformation_api.cityjson.models import CityjsonV113
from coordinates_transformation_api.models import Crs as MyCrs
from coordinates_transformation_api.models import CrsFeatureCollection
from coordinates_transformation_api.settings import app_settings

GeojsonGeomNoGeomCollection = (
    Point | MultiPoint | LineString | MultiLineString | Polygon | MultiPolygon
)

GeojsonCoordinates = (
    Position
    | PolygonCoords
    | LineStringCoords
    | MultiPointCoords
    | MultiLineStringCoords
    | MultiPolygonCoords
)


logger = logging.getLogger(__name__)

coordinates_type = tuple[float, float] | tuple[float, float, float] | list[float]
TWO_DIMENSIONAL = 2
THREE_DIMENSIONAL = 3

DENSIFY_CRS = "EPSG:4258"
DEVIATION_VALID_BBOX = [
    3.1201,
    50.2191,
    7.5696,
    54.1238,
]  # bbox in epsg:4258 - area valid for doing density check (based on deviation param)


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
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                f"number of dimensions of target-crs should be equal or less then that of the source-crs\n * source-crs: {source_crs}, dimensions: {source_crs_dims}\n * target-crs {target_crs}, dimensions: {target_crs_dims}",
                            ),
                            loc=("query", "target-crs"),
                            input=(source_crs, target_crs),
                        )
                    ],
                )
            ).errors()
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
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                "number of coordinates must match number of dimensions of source-crs",
                            ),
                            loc=("query", "coordinates"),
                            input=source_crs,
                        )
                    ],
                )
            ).errors()
        )


def validate_input_max_segment_deviation_length(deviation, length):
    if length is None and deviation is None:
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                "max_segment_length or max_segment_deviation should be set",
                            ),
                            loc=("query", "max_segment_length|max_segment_deviation"),
                            input=[None, None],
                        )
                    ],
                )
            ).errors()
        )


def validate_input_crs(value, name, projections_axis_info: list[MyCrs]):
    if not any(
        crs for crs in projections_axis_info if crs.crs_auth_identifier == value
    ):
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                f"{name} should be one of {', '.join([str(x.crs_auth_identifier) for x in projections_axis_info])}",
                            ),
                            loc=("query", name),
                            input=value,
                        )
                    ],
                )
            ).errors()
        )


class AxisInfo(TypedDict):
    axis_labels: list[str]
    dimensions: int


def get_precision(target_crs_crs: MyCrs):
    precision = app_settings.precision
    unit = target_crs_crs.get_x_unit_crs()
    if unit == "degree":
        precision += 5
    return precision


def traverse_geojson_coordinates(
    geojson_coordinates: list[list] | list[float] | list[int],
    callback: Callable[
        [coordinates_type],
        tuple[float, ...],
    ],
):
    """traverse GeoJSON coordinates object and apply callback function to coordinates-nodes

    Args:
        obj: GeoJSON coordinates object
        callback (): callback function to transform coordinates-nodes

    Returns:
        GeoJSON coordinates object
    """
    if all(isinstance(x, (float, int)) for x in geojson_coordinates):
        return callback(cast(list[float], geojson_coordinates))
    else:
        coords = cast(list[list], geojson_coordinates)
        return [
            traverse_geojson_coordinates(elem, callback=callback) for elem in coords
        ]


def extract_authority_code(crs: str) -> str:
    r = re.search("^(http://www.opengis.net/def/crs/)?(.[^/|:]*)(/.*/|:)(.*)", crs)
    if r is not None:
        return str(r[2] + ":" + r[4])

    return crs


def format_as_uri(crs: str) -> str:
    # TODO: the /0/ is a placeholder and should be based on the epsg database version
    #   discuss what convention we want to follow here...
    return "http://www.opengis.net/def/crs/{}/0/{}".format(*crs.split(":"))


def validate_crss(source_crs: str, target_crs: str, projections_axis_info):
    validate_input_crs(source_crs, "source-crs", projections_axis_info)
    validate_input_crs(target_crs, "target_crs", projections_axis_info)
    validate_crs_transformation(source_crs, target_crs, projections_axis_info)


def explode(coords):
    """Explode a GeoJSON geometry's coordinates object and yield coordinate tuples.
    As long as the input is conforming, the type of the geometry doesn't matter.
    Source: https://gis.stackexchange.com/a/90554
    """
    for e in coords:
        if isinstance(
            e,
            (
                float,
                int,
            ),
        ):
            yield coords
            break
        else:
            yield from explode(e)


def get_bbox_from_coordinates(coordinates) -> BBox:
    coordinate_tuples = list(zip(*list(explode(coordinates))))
    if len(coordinate_tuples) == TWO_DIMENSIONAL:
        x, y = coordinate_tuples
        return min(x), min(y), max(x), max(y)
    elif len(coordinate_tuples) == THREE_DIMENSIONAL:
        x, y, z = coordinate_tuples
        return min(x), min(y), min(z), max(x), max(y), max(z)
    else:
        raise ValueError(
            f"expected length of coordinate tuple is either 2 or 3, got {len(coordinate_tuples)}"
        )


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


def get_source_crs_body(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection | CityjsonV113,
) -> str | None:
    if isinstance(body, CrsFeatureCollection) and body.crs is not None:
        source_crs = body.get_crs_auth_code()
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


def get_coordinates_from_geometry(
    item: _GeometryBase,
) -> list:
    geom = cast(_GeometryBase, item)
    return list(
        chain(explode(geom.coordinates))
    )  # TODO: check if chain(list()) is required...


def accept_html(request: Request) -> bool:
    if "accept" in request.headers:
        accept_header = request.headers["accept"]
        if "text/html" in accept_header:
            return True
    return False


def request_body_within_valid_bbox(body, source_crs):
    if source_crs != DENSIFY_CRS:
        transform_f = get_transform_callback(DENSIFY_CRS, source_crs)
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


def apply_function_on_geometries_of_request_body(  # noqa: C901
    body: Feature
    | CrsFeatureCollection
    | GeojsonGeomNoGeomCollection
    | GeometryCollection,
    callback: Callable[
        [GeojsonGeomNoGeomCollection, list[Any], list[int] | None], None
    ],
    indices: list[int] | None = None,
) -> Any:
    result: list[Any] = []
    if isinstance(body, Feature):
        feature = cast(Feature, body)
        if isinstance(feature.geometry, GeometryCollection):
            return apply_function_on_geometries_of_request_body(
                feature.geometry, callback
            )

        geom = cast(GeojsonGeomNoGeomCollection, feature.geometry)
        return callback(geom, result, None)
    elif isinstance(body, GeojsonGeomNoGeomCollection):  # type: ignore
        geom = cast(GeojsonGeomNoGeomCollection, body)
        return callback(geom, result, indices)
    elif isinstance(body, CrsFeatureCollection):
        fc_body: CrsFeatureCollection = body
        features: Iterable[Feature] = fc_body.features
        for i, ft in enumerate(features):
            if ft.geometry is None:
                raise ValueError(f"feature does not have a geometry, feature: {ft}")
            if isinstance(ft.geometry, GeometryCollection):
                ft_result = apply_function_on_geometries_of_request_body(
                    ft.geometry, callback, [i]
                )
                result.extend(ft_result)
            else:
                callback(ft.geometry, result, [i])
    elif isinstance(body, GeometryCollection):
        gc = cast(GeometryCollection, body)
        geometries: list[Geometry] = gc.geometries
        for i, g in enumerate(geometries):
            n_indices = None
            if indices is not None:
                n_indices = indices[:]
                n_indices.append(i)
            g_no_gc = cast(
                GeojsonGeomNoGeomCollection, g
            )  # geojson prohibits nested geometrycollections - maybe throw exception if this occurs
            callback(g_no_gc, result, n_indices)
    return result


def get_shapely_objects(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection,
) -> list[Any]:
    def merge_geometry_collections_shapelyfication(input_shp_geoms: list) -> list:
        indices = list(map(lambda x: x["index"][0], input_shp_geoms))
        counter = Counter(indices)
        geom_coll_indices = [x for x in counter if counter[x] > 1]
        output_shp_geoms = [
            x["result"]
            for x in input_shp_geoms
            if x["index"][0] not in geom_coll_indices
        ]
        for i in geom_coll_indices:
            geom_collection_geoms = [
                x["result"] for x in input_shp_geoms if x["index"][0] == i
            ]
            output_shp_geoms.append(ShpGeometryCollection(geom_collection_geoms))
        return output_shp_geoms

    transform_fun = get_shapely_object_fun()
    result = apply_function_on_geometries_of_request_body(body, transform_fun)
    return merge_geometry_collections_shapelyfication(result)


def get_shapely_object_fun() -> Callable:
    def shapely_object(
        geometry_dict: dict[str, Any], result: list, indices: list[int] | None = None
    ) -> None:
        shp_obj = shape(geometry_dict)
        result_item = {"result": shp_obj}
        if indices is not None:
            result_item["index"] = indices
        result.append(result_item)

    return shapely_object


def get_density_check_fun(
    densify_config: DenseConfig,
) -> Callable:
    def density_check(
        geometry: GeojsonGeomNoGeomCollection,
        result: list,
        indices: list[int] | None = None,
    ) -> None:
        check_density_geometry_coordinates(
            geometry.coordinates, densify_config, result, indices
        )

    return density_check


def get_update_geometry_bbox_fun() -> Callable:
    def update_bbox(
        geometry: GeojsonGeomNoGeomCollection,
        _result: list,
        _indices: list[int] | None = None,
    ) -> None:
        coordinates = get_coordinates_from_geometry(geometry)
        geometry.bbox = get_bbox_from_coordinates(coordinates)

    return update_bbox


def update_bbox_geojson_object(  # noqa: C901
    geojson_obj: Feature | CrsFeatureCollection | Geometry | GeometryCollection,
) -> None:
    def rec_fun(  # noqa: C901
        geojson_obj: Feature | CrsFeatureCollection | Geometry | GeometryCollection,
    ) -> list:
        if isinstance(geojson_obj, CrsFeatureCollection):
            fc_coords: list = []
            for ft in geojson_obj.features:
                fc_coords.append(rec_fun(ft))
            if geojson_obj.bbox is not None:
                geojson_obj.bbox = get_bbox_from_coordinates(fc_coords)
            return fc_coords
        elif isinstance(geojson_obj, Feature):
            ft_coords: list = []
            if geojson_obj.geometry is None:
                return ft_coords
            ft_coords = rec_fun(geojson_obj.geometry)
            if geojson_obj.bbox is not None:
                geojson_obj.bbox = get_bbox_from_coordinates(ft_coords)
            return ft_coords
        elif isinstance(geojson_obj, GeometryCollection):
            gc_coords: list = []
            for geom in geojson_obj.geometries:
                gc_coords.append(rec_fun(geom))
            if geojson_obj.bbox is not None:
                geojson_obj.bbox = get_bbox_from_coordinates(gc_coords)
            return gc_coords
        elif isinstance(geojson_obj, _GeometryBase):
            geom_coords: list = get_coordinates_from_geometry(geojson_obj)
            if geojson_obj.bbox is not None:
                geojson_obj.bbox = get_bbox_from_coordinates(geom_coords)
            return geom_coords

    _ = rec_fun(geojson_obj)


def crs_transform(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection,
    s_crs: str,
    t_crs: str,
    epoch: float | None = None,
) -> None:
    crs_transform_fun = get_crs_transform_fun(s_crs, t_crs, epoch)
    _ = apply_function_on_geometries_of_request_body(body, crs_transform_fun)
    if isinstance(body, CrsFeatureCollection):
        body.set_crs_auth_code(t_crs)
    update_bbox_geojson_object(body)


def get_validate_json_coords_fun() -> Callable:
    def validate_json_coords(
        geometry: GeojsonGeomNoGeomCollection,
        _result: list,
        _indices: list[int] | None = None,
    ) -> None:
        def coords_has_inf(coordinates):
            gen = (
                x
                for x in explode(coordinates)
                if abs(x[0]) == float("inf") or abs(x[1]) == float("inf")
            )
            return next(gen, None) is not None

        coordinates = get_coordinates_from_geometry(geometry)
        if coords_has_inf(coordinates):
            raise_response_validation_error(
                "Out of range float values are not JSON compliant", ["responseBody"]
            )

    return validate_json_coords


def density_check_request_body(
    body: Feature | CrsFeatureCollection | Geometry | GeometryCollection,
    source_crs: str,
    max_segment_deviation: float,
    max_segment_length: float,
) -> list[tuple[list[int], float]]:
    report: list[tuple[list[int], float]] = []

    # TODO: figure out how to handle point geometries - what to do if point geometry in payload as part of featurecollection/geometrycollection
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
    report = apply_function_on_geometries_of_request_body(body, my_fun)
    return report


def bbox_check_deviation_set(body, source_crs, max_segment_deviation):
    if max_segment_deviation is None and not request_body_within_valid_bbox(
        body, source_crs
    ):
        # request body not within valid bbox todo density check
        # TODO: raise error
        print("body not inside bbox")


def get_densify_fun(
    densify_config: DenseConfig,
) -> Callable:
    def my_fun(
        geometry: Geometry, _result: list, _indices: list[int] | None = None
    ):  # add _result, _indices args since required by transform_geometries_req_body
        geoms: list[Geometry] = []
        if isinstance(geometry, _GeometryBase):
            geoms = [geometry]
        elif isinstance(geometry, GeometryCollection):
            geoms = geometry.geometries

        for g in geoms:
            g_base = cast(_GeometryBase, g)
            g_base.coordinates = densify_geometry_coordinates(
                g_base.coordinates, densify_config
            )

    return my_fun


def densify_request_body(
    body: Feature | CrsFeatureCollection | Geometry,
    source_crs: str,
    max_segment_deviation: float,
    max_segment_length: float,
) -> None:
    """transform coordinates of request body in place

    Args:
        body (Feature | FeatureCollection | _GeometryBase | GeometryCollection): request body to transform, will be transformed in place
        transformer (Transformer): pyproj Transformer object
    """
    # TODO: figure out how to handle point geometries - what to do if point geometry in payload as part of featurecollection/geometrycollection
    validate_input_max_segment_deviation_length(
        max_segment_deviation, max_segment_length
    )
    bbox_check_deviation_set(body, source_crs, max_segment_deviation)
    if max_segment_deviation is not None:
        max_segment_length = convert_deviation_to_distance(max_segment_deviation)

    crs_transform(body, source_crs, DENSIFY_CRS)

    # densify request body
    c = DenseConfig(CRS.from_authority(*DENSIFY_CRS.split(":")), max_segment_length)
    densify_fun = get_densify_fun(c)
    _ = apply_function_on_geometries_of_request_body(body, densify_fun)

    crs_transform(body, DENSIFY_CRS, source_crs)  # transform back


def get_crs_transform_fun(source_crs, target_crs, epoch) -> Callable:
    target_crs_crs: MyCrs = MyCrs.from_crs_str(target_crs)
    precision = get_precision(target_crs_crs)

    def my_fun(
        geom: GeojsonGeomNoGeomCollection,
        _result: list,
        _indices: list[int] | None = None,
    ) -> (
        None
    ):  # add _result, _indices args since required by transform_geometries_req_body
        callback = get_transform_callback(
            source_crs, target_crs, precision, epoch=epoch
        )
        geom.coordinates = traverse_geojson_coordinates(
            cast(list[list[Any]] | list[float] | list[int], geom.coordinates),
            callback=callback,
        )

    return my_fun


def init_oas() -> tuple[dict, str, str]:
    """initialize open api spec:
    - extract api version string from oas
    - return projection info from oas

    Returns:
        Tuple[dict, str, dict]: _description_
    """
    oas_filepath = impresources.files(assets) / "openapi.yaml"

    with oas_filepath.open("rb") as oas_file:
        oas = yaml.load(oas_file, yaml.SafeLoader)
        crs_param_description = ""
        oas["components"]["parameters"]["source-crs"][
            "description"
        ] = f"Source Coordinate Reference System\n{crs_param_description}"
        oas["components"]["parameters"]["target-crs"][
            "description"
        ] = f"Target Coordinate Reference System\n{crs_param_description}"
        servers = [{"url": app_settings.base_url}]
        oas["servers"] = servers
    api_version = oas["info"]["version"]
    api_title = oas["info"]["title"]
    return (oas, api_title, api_version)


def convert_distance_to_deviation(d):
    a = 24.15 * 10**-9 * d**2
    return a


def convert_deviation_to_distance(a):
    d = math.sqrt(a / (24.15 * 10**-9))
    return d
