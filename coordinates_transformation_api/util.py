from importlib import resources as impresources
from typing import Callable, Iterable, Tuple, Union, cast

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

from coordinates_transformation_api import assets

logger = logging.getLogger(__name__)


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
    def callback(
        val: Union[Tuple[float, float], Tuple[float, float, float]]
    ) -> Tuple[float, ...]:
        if transformer.target_crs is None:
            raise ValueError("transformer.target_crs is None")
        dim = len(transformer.target_crs.axis_info)
        if dim != None and dim != len(val):
            if (
                2 > dim > 3
            ):  # check so we can safely cast to Tuple[float, float], Tuple[float, float, float]
                raise ValueError(
                    f"number of dimensions of target-crs should be 2 or 3, is {dim}"
                )
            val = cast(
                Union[Tuple[float, float], Tuple[float, float, float]], val[0:dim]
            )
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

    def transform_geom(
        transformer: Transformer, geom: GeojsonGeomNoGeomCollection
    ) -> None:
        geom.coordinates = traverse_geojson_coordinates(
            geom.coordinates, callback=get_transform_callback(transformer)
        )

    if isinstance(body, Feature):
        feature = cast(Feature, body)
        transform_feature(transformer, transform_geom, feature)
    elif isinstance(body, FeatureCollection):
        fc_body: FeatureCollection = body
        features: Iterable[Feature] = fc_body.features
        for feature in features:
            transform_feature(transformer, transform_geom, feature)
    elif isinstance(body, _GeometryBase):
        geom = cast(GeojsonGeomNoGeomCollection, body)
        transform_geom(transformer, geom)
    elif isinstance(body, GeometryCollection):
        gc = cast(GeometryCollection, body)
        transform_geometry_collection(transformer, transform_geom, gc)


def transform_geometry_collection(
    transformer: Transformer,
    transform_geom: Callable[[Transformer, GeojsonGeomNoGeomCollection], None],
    gc: GeometryCollection,
) -> None:
    geometries: list[Geometry] = gc.geometries
    for g in geometries:
        geom = cast(GeojsonGeomNoGeomCollection, g)
        transform_geom(transformer, geom)


def transform_feature(
    transformer: Transformer,
    transform_geom: Callable[[Transformer, GeojsonGeomNoGeomCollection], None],
    feature: Feature,
) -> None:
    if isinstance(feature.geometry, GeometryCollection):
        gc = cast(GeometryCollection, feature.geometry)
        transform_geometry_collection(transformer, transform_geom, gc)
    else:
        geom = cast(GeojsonGeomNoGeomCollection, feature.geometry)
        transform_geom(transformer, geom)


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
