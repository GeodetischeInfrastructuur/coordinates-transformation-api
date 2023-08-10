from importlib import resources as impresources
from typing import Any, Iterable, Tuple

import yaml
from fastapi.exceptions import RequestValidationError
from geojson_pydantic import Feature, FeatureCollection
from geojson_pydantic.geometries import (Geometry, GeometryCollection,
                                         _GeometryBase)
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from pyproj import CRS, Transformer

from coordinates_transformation_api import assets


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
                            type=PydanticCustomError(
                                "value_error",
                                f"number of coordinates in request body ({coordinates_count}) exceeds MAX_NR_COORDINATES ({max_nr_coordinates})",
                            ),
                            loc=("body"),
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
        geojson_coordinates: list[any] | list[float] | list[int],
    ) -> None:
        nonlocal count
        if all(isinstance(x, float) or isinstance(x, int) for x in geojson_coordinates):
            count += len(geojson_coordinates)
        elif isinstance(geojson_coordinates, list):
            return [traverse_count(elem) for elem in geojson_coordinates]

    traverse_count(geojson_coordinates)
    return count


from typing import Any


def count_coordinate_nodes_object(
    input: Feature | FeatureCollection | _GeometryBase | GeometryCollection,
) -> int:
    # handle collections first
    if isinstance(input, FeatureCollection | GeometryCollection):
        if isinstance(input, FeatureCollection):
            fc: FeatureCollection = input
            features: Iterable[Feature] = fc.features
            coordinates: Iterable[Any] = [x.geometry.coordinates for x in features]
        elif isinstance(input, GeometryCollection):
            geometries: Iterable[Geometry] = input
            coordinates: Iterable[Any] = [x.coordinates for x in geometries]

        if len(coordinates) > 0:
            return sum([count_coordinates_nodes(x) for x in coordinates])
    else:
        if isinstance(input, Feature):
            ft: Feature = input
            single_coordinates: Any = ft.geometry.coordinates
        if isinstance(input, _GeometryBase):
            geometry: _GeometryBase = input
            single_coordinates: Any = geometry.coordinates
        return count_coordinates_nodes(single_coordinates)


def validate_crss(source_crs: str, target_crs: str, projections_axis_info: dict):
    validate_input_crs(source_crs, "source-crs", projections_axis_info)
    validate_input_crs(target_crs, "target_crs", projections_axis_info)
    validate_crs_transformation(source_crs, target_crs, projections_axis_info)


def get_transformer(source_crs: str, target_crs: str):
    source_crs_crs = CRS.from_authority(*source_crs.split(":"))
    target_crs_crs = CRS.from_authority(*target_crs.split(":"))
    transformer = Transformer.from_crs(source_crs_crs, target_crs_crs)

    return transformer


def get_transform_callback(transformer: Transformer):
    def callback(val: tuple[float]) -> tuple[float]:
        dim = len(transformer.target_crs.axis_info)

        if dim != None and dim != len(val):
            val = val[0:dim]

        return tuple([round(x, 6) for x in transformer.transform(*val)])

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

    def transform_geom(transformer: Transformer, geom: _GeometryBase) -> None:
        geom.coordinates = traverse_geojson_coordinates(
            geom.coordinates, callback=get_transform_callback(transformer)
        )

    if isinstance(body, Feature):
        feature_body: Feature = body
        geom: Geometry = feature_body.geometry
        transform_geom(transformer, geom)
    elif isinstance(body, FeatureCollection):
        fc_body: FeatureCollection = body
        features: Iterable[Feature] = fc_body.features
        for feature in features:
            transform_geom(transformer, feature.geometry)
    elif isinstance(body, _GeometryBase):
        geom: Geometry = body
        transform_geom(transformer, geom)
    elif isinstance(body, GeometryCollection):
        geometries: Iterable[Geometry] = body
        for geometry in geometries:
            transform_geom(transformer, geometry)


def init_oas() -> Tuple[dict, str, dict]:
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
    return (oas, api_version, projs_axis_info)
