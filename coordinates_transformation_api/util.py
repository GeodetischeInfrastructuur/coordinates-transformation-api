from importlib import resources as impresources
from typing import Any, Iterable, Tuple, Union, cast

import yaml
from fastapi.exceptions import RequestValidationError
from geojson_pydantic import (Feature, FeatureCollection, LineString,
                              MultiLineString, MultiPoint, MultiPolygon, Point,
                              Polygon)
from geojson_pydantic.geometries import (Geometry, GeometryCollection,
                                         _GeometryBase)
from geojson_pydantic.types import (LineStringCoords, MultiLineStringCoords,
                                    MultiPointCoords, MultiPolygonCoords,
                                    PolygonCoords, Position)
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from pyproj import CRS, Transformer

GeojsonGeomNoGeomCollection = Union[
    Point,
    MultiPoint,
    LineString,
    MultiLineString,
    Polygon,
    MultiPolygon,
]

GeojsonCoordinates = Union[
    Position,
    PolygonCoords,
    LineStringCoords,
    MultiPointCoords,
    MultiLineStringCoords,
    MultiPolygonCoords,
]

import logging
from typing import Any

from coordinates_transformation_api import assets

logger = logging.getLogger(__name__)


def validate_coordinates_limit(
    body: Feature | FeatureCollection | _GeometryBase | GeometryCollection,
    max_nr_coordinates: int,
):
    coordinates_count = count_coordinate_nodes_object(body)
    if coordinates_count > max_nr_coordinates:
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            # TODO: fix loc field in error
                            type=PydanticCustomError(
                                "value_error",
                                f"number of coordinates in request body ({coordinates_count}) exceeds MAX_NR_COORDINATES ({max_nr_coordinates})",
                            ),
                            loc=tuple("body"),
                            input=body,
                        )
                    ],
                )
            ).errors()
        )


def validate_crs_transformation(source_crs, target_crs, projections_axis_info):
    source_crs_dims = projections_axis_info[source_crs]["dimensions"]
    target_crs_dims = projections_axis_info[target_crs]["dimensions"]

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
                        )
                    ],
                )
            ).errors()
        )


def validate_coords_source_crs(coordinates, source_crs, projections_axis_info):
    source_crs_dims = projections_axis_info[source_crs]["dimensions"]
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
                        )
                    ],
                )
            ).errors()
        )


def validate_input_crs(value, name, projections_axis_info):
    if value not in projections_axis_info.keys():
        raise RequestValidationError(
            errors=(
                ValidationError.from_exception_data(
                    "ValueError",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError(
                                "value_error",
                                f"{name} should be one of {', '.join(projections_axis_info.keys())}",
                            ),
                            loc=("query", name),
                        )
                    ],
                )
            ).errors()
        )


def get_projs_axis_info(proj_strings):
    result = {}
    for proj_string in proj_strings:
        crs = CRS.from_authority(*proj_string.split(":"))
        nr_dim = len(crs.axis_info)
        axis_labels = list(map(lambda x: f"{x.abbrev} ({x.unit_name})", crs.axis_info))
        axis_info_summary = {"dimensions": nr_dim, "axis_labels": axis_labels}
        result[proj_string] = axis_info_summary
    return result


def traverse_geojson_coordinates(geojson_coordinates, callback):
    """traverse GeoJSON coordinates object and apply callback function to coordinates-nodes

    Args:
        obj: GeoJSON coordinates object
        callback (): callback function to transform coordinates-nodes

    Returns:
        GeoJSON coordinates object
    """
    if all(isinstance(x, float) or isinstance(x, int) for x in geojson_coordinates):
        return callback(geojson_coordinates)
    elif isinstance(geojson_coordinates, list):
        return [
            traverse_geojson_coordinates(elem, callback=callback)
            for elem in geojson_coordinates
        ]


def count_coordinates_nodes(geojson_coordinates: Any) -> int:
    count = 0

    def traverse_count(
        geojson_coordinates: list[Any] | list[float] | list[int],
    ):
        nonlocal count
        if all(isinstance(x, float) or isinstance(x, int) for x in geojson_coordinates):
            count += len(geojson_coordinates)
        elif isinstance(geojson_coordinates, list):
            for elem in geojson_coordinates:
                elem_any: list[Any] = cast(list[Any], elem)
                traverse_count(elem_any)

    traverse_count(geojson_coordinates)
    return count


def get_geom(in_geom: Union[Geometry, Any, None]) -> GeojsonGeomNoGeomCollection:
    return cast(
        GeojsonGeomNoGeomCollection,
        in_geom,
    )


def get_coordinates_from_geometry(
    geom: GeojsonGeomNoGeomCollection,
) -> GeojsonCoordinates:
    return geom.coordinates


def get_coordinates_from_feature(
    ft: Feature,
) -> Union[GeojsonCoordinates, list[GeojsonCoordinates]]:
    geom: Geometry
    if isinstance(geom, GeometryCollection):
        gc: GeometryCollection = cast(GeometryCollection, geom)
        result = []
        for x in gc.geometries:
            y = cast(
                GeojsonGeomNoGeomCollection,
                x,
            )
            result.append(y.coordinates)
        return result
    else:
        geom = get_geom(ft.geometry)
        return geom.coordinates


def count_coordinate_nodes_object(
    input: Feature | FeatureCollection | _GeometryBase | GeometryCollection,
) -> int:
    # handle collections first
    if isinstance(input, FeatureCollection | GeometryCollection):
        coordinates: Iterable[Any]
        if isinstance(input, FeatureCollection):
            fc: FeatureCollection = input
            features: Iterable[Feature] = fc.features
            coordinates = [get_coordinates_from_feature(x) for x in features]
        elif isinstance(input, GeometryCollection):
            geometries: Iterable[Geometry] = input.geometries
            coordinates = [
                get_coordinates_from_geometry(get_geom(x)) for x in geometries
            ]

        return sum([count_coordinates_nodes(x) for x in coordinates])
    else:
        if isinstance(input, Feature):
            ft: Feature = input
            geometry = cast(Geometry, ft.geometry)

        if isinstance(input, _GeometryBase):
            geometry = cast(Geometry, input)

        c = cast(
            GeojsonGeomNoGeomCollection,
            geometry,
        )
        single_coordinates = cast(
            GeojsonCoordinates,
            c.coordinates,
        )
        return count_coordinates_nodes(single_coordinates)


def get_transform_callback(transformer: Transformer):
    def callback(
        val: Union[Tuple[float, float], Tuple[float, float, float]]
    ) -> tuple[float, ...]:
        return tuple([float(round(x, 6)) for x in transformer.transform(*val)])

    return callback


def transform_request_body(
    body: Feature | FeatureCollection | _GeometryBase | GeometryCollection,
    transformer: Transformer,
) -> None:
    """transform coordinates of request body in place

    Args:
        body (Feature | FeatureCollection | _GeometryBase | GeometryCollection): request body to transform, will be transformed in place
        transformer (Transformer): pyproj Transformer object
    """

    # TODO: fix type annotation geom object
    def transform_geom(transformer: Transformer, geom: Any) -> None:
        geom.coordinates = traverse_geojson_coordinates(
            geom.coordinates, callback=get_transform_callback(transformer)
        )

    if isinstance(body, Feature):
        feature_body: Feature = body
        geom = feature_body.geometry
        transform_geom(transformer, geom)
    elif isinstance(body, FeatureCollection):
        fc_body: FeatureCollection = body
        features: Iterable[Feature] = fc_body.features
        for feature in features:
            geom = feature.geometry
            transform_geom(transformer, geom)
    elif isinstance(body, _GeometryBase):
        geom = body
        transform_geom(transformer, geom)
    elif isinstance(body, GeometryCollection):
        geometries: Iterable[Geometry] = body
        for geometry in geometries:
            transform_geom(transformer, geometry)


def init_oas() -> Tuple[dict, str, str, dict]:
    """initialize open api spec:
    - enrich crs parameters with description generated from pyproj
    - extract api verion string from oas
    - return projection info from oas

    Returns:
        Tuple[dict, str, dict]: _description_
    """
    oas_filepath = impresources.files(assets) / "openapi.yaml"

    with oas_filepath.open("rb") as oas_file:
        oas = yaml.load(oas_file, yaml.SafeLoader)
        crs_identifiers = oas["components"]["schemas"]["crs"]["enum"]
        projs_axis_info = get_projs_axis_info(crs_identifiers)
        crs_param_description = ""
        for key in projs_axis_info.keys():
            crs_param_description += f"* `{key}`: format: `{', '.join(projs_axis_info[key]['axis_labels'])}`, dimensions: {projs_axis_info[key]['dimensions']}\n"  # ,
        oas["components"]["parameters"]["source-crs"][
            "description"
        ] = f"Source Coordinate Reference System\n{crs_param_description}"
        oas["components"]["parameters"]["target-crs"][
            "description"
        ] = f"Target Coordinate Reference System\n{crs_param_description}"
    api_version = oas["info"]["version"]
    api_title = oas["info"]["title"]
    return (oas, api_title, api_version, projs_axis_info)
