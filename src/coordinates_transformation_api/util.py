from importlib import resources as impresources
from itertools import chain
from typing import Any, Callable, Iterable, Tuple, TypedDict, Union, cast

import yaml
from fastapi.exceptions import RequestValidationError
from geojson_pydantic import (Feature, FeatureCollection, LineString,
                              MultiLineString, MultiPoint, MultiPolygon, Point,
                              Polygon)
from geojson_pydantic.geometries import (Geometry, GeometryCollection,
                                         _GeometryBase)
from geojson_pydantic.types import (BBox, LineStringCoords,
                                    MultiLineStringCoords, MultiPointCoords,
                                    MultiPolygonCoords, PolygonCoords,
                                    Position)
from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError
from pyproj import CRS, Transformer

from coordinates_transformation_api.cityjson.models import CityjsonV113
from coordinates_transformation_api.models import Axis
from coordinates_transformation_api.models import Crs as MyCrs
from coordinates_transformation_api.models import CrsFeatureCollection

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


def validate_crs_transformation(
    source_crs, target_crs, projections_axis_info: list[MyCrs]
):
    source_crs_dims = [
        crs.nr_of_dimensions
        for crs in projections_axis_info
        if crs.crs_auth_identifier == source_crs
    ][0]
    target_crs_dims = [
        crs.nr_of_dimensions
        for crs in projections_axis_info
        if crs.crs_auth_identifier == target_crs
    ][0]

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
    source_crs_dims = [
        crs.nr_of_dimensions
        for crs in projections_axis_info
        if crs.crs_auth_identifier == source_crs
    ][0]
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


def get_projs_axis_info(proj_strings) -> list[MyCrs]:
    result: list[MyCrs] = []
    for proj_string in proj_strings:
        auth, identifier = proj_string.split(":")
        crs = CRS.from_authority(auth, identifier)
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
        my_crs = MyCrs(
            name=crs.name,
            type_name=crs.type_name,
            crs_auth_identifier=crs.srs,
            axes=axes,
            authority=auth,
            identifier=identifier,
        )
        result.append(my_crs)
    return result


def traverse_geojson_coordinates(
    geojson_coordinates: Union[list[list], list[float], list[int]],
    callback: Callable[
        [Union[tuple[float, float], tuple[float, float, float], list[float]]],
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
    if all(isinstance(x, float) or isinstance(x, int) for x in geojson_coordinates):
        return callback(cast(list[float], geojson_coordinates))
    else:
        coords = cast(list[list], geojson_coordinates)
        return [
            traverse_geojson_coordinates(elem, callback=callback) for elem in coords
        ]


def validate_crss(source_crs: str, target_crs: str, projections_axis_info):
    validate_input_crs(source_crs, "source-crs", projections_axis_info)
    validate_input_crs(target_crs, "target_crs", projections_axis_info)
    validate_crs_transformation(source_crs, target_crs, projections_axis_info)


def get_transformer(source_crs: str, target_crs: str):
    source_crs_crs = CRS.from_authority(*source_crs.split(":"))
    target_crs_crs = CRS.from_authority(*target_crs.split(":"))
    transformer = Transformer.from_crs(source_crs_crs, target_crs_crs, always_xy=True)
    return transformer


def get_transform_callback(
    transformer: Transformer, precision: int | None = None
) -> Callable[
    [Union[tuple[float, float], tuple[float, float, float], list[float]]],
    tuple[float, ...],
]:
    """TODO: improve type annotation/handling geojson/cityjson transformation, with the current implementation mypy is not complaining"""

    def my_round(val, precision: int | None):
        if precision is None:
            return val
        else:
            return round(val, precision)

    def callback(
        val: Union[tuple[float, float], tuple[float, float, float], list[float]]
    ) -> tuple[float, ...]:
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
        val = cast(Union[Tuple[float, float], Tuple[float, float, float]], val[0:dim])

        # GeoJSON and CityJSON by definition has coordinates always in lon-lat-height (or x-y-z) order. Transformer has been created with `always_xy=True`,
        # to ensure input and output coordinates are in in lon-lat-height (or x-y-z) order.
        return tuple(
            [float(my_round(x, precision)) for x in transformer.transform(*val)]
        )

    return callback


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
            for f in explode(e):
                yield f


def get_bbox_from_coordinates(coordinates) -> BBox:
    coordinate_tuples = list(zip(*list(explode(coordinates))))
    if len(coordinate_tuples) == 2:
        x, y = coordinate_tuples
        return min(x), min(y), max(x), max(y)
    elif len(coordinate_tuples) == 3:
        x, y, z = coordinate_tuples
        return min(x), min(y), min(z), max(x), max(y), max(z)
    else:
        raise ValueError(
            f"expected length of coordinate tuple is either 2 or 3, got {len(coordinate_tuples)}"
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
    body: Union[Feature, CrsFeatureCollection, Geometry, GeometryCollection]
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


def get_bbox(
    item: Feature | FeatureCollection | _GeometryBase | GeometryCollection,
) -> BBox:
    if isinstance(item, _GeometryBase) or isinstance(item, GeometryCollection):
        coordinates = get_coordinates_from_geometry(item)
    elif isinstance(item, Feature):
        geometry = cast(Geometry, item.geometry)
        coordinates = get_coordinates_from_geometry(geometry)
    elif isinstance(item, FeatureCollection):
        features: Iterable[Feature] = item.features
        coordinates = [
            get_coordinates_from_geometry(cast(Geometry, ft.geometry))
            for ft in features
        ]
    return get_bbox_from_coordinates(coordinates)


def get_coordinates_from_geometry(
    item: _GeometryBase | GeometryCollection,
) -> Iterable[
    Position | MultiPointCoords | MultiLineStringCoords | MultiPolygonCoords | Any
]:
    if isinstance(item, _GeometryBase):
        geom = cast(_GeometryBase, item)
        return chain(explode(geom.coordinates))
    elif isinstance(item, GeometryCollection):
        geom_collection = cast(GeometryCollection, item)
        geometries: Iterable[GeojsonGeomNoGeomCollection] = [
            cast(GeojsonGeomNoGeomCollection, x) for x in geom_collection.geometries
        ]
        return chain(*[explode(y.coordinates) for y in geometries])


def transform_request_body(
    body: Feature | CrsFeatureCollection | _GeometryBase | GeometryCollection,
    transformer: Transformer,
) -> None:
    """transform coordinates of request body in place

    Args:
        body (Feature | FeatureCollection | _GeometryBase | GeometryCollection): request body to transform, will be transformed in place
        transformer (Transformer): pyproj Transformer object
    """

    def transform_geom(geom: GeojsonGeomNoGeomCollection) -> None:
        callback = get_transform_callback(transformer, 6)
        geom.coordinates = traverse_geojson_coordinates(
            cast(list[list[Any]] | list[float] | list[int], geom.coordinates),
            callback=callback,
        )
        if geom.bbox is not None:
            geom.bbox = get_bbox(geom)

    if isinstance(body, Feature):
        feature = cast(Feature, body)
        transform_feature(transform_geom, feature)
        if feature.bbox is not None:
            feature.bbox = get_bbox(feature)
    elif isinstance(body, CrsFeatureCollection):
        fc_body: CrsFeatureCollection = body
        features: Iterable[Feature] = fc_body.features
        for feature in features:
            transform_feature(transform_geom, feature)
        if fc_body.bbox is not None:
            fc_body.bbox = get_bbox(fc_body)
        if fc_body.crs is not None:
            target_crs = cast(
                CRS, transformer.target_crs
            )  # transformer always has a target_crs
            fc_body.set_crs_auth_code(target_crs.to_string())
    elif isinstance(body, _GeometryBase):
        geom = cast(GeojsonGeomNoGeomCollection, body)
        transform_geom(geom)
    elif isinstance(body, GeometryCollection):
        gc = cast(GeometryCollection, body)
        transform_geometry_collection(transform_geom, gc)


def transform_geometry_collection(
    transform_geom: Callable[[GeojsonGeomNoGeomCollection], None],
    gc: GeometryCollection,
) -> None:
    geometries: list[Geometry] = gc.geometries
    for g in geometries:
        geom = cast(GeojsonGeomNoGeomCollection, g)
        transform_geom(geom)
    if gc.bbox is not None:
        gc.bbox = get_bbox(gc)


def transform_feature(
    transform_geom: Callable[[GeojsonGeomNoGeomCollection], None],
    feature: Feature,
) -> None:
    if isinstance(feature.geometry, GeometryCollection):
        gc = cast(GeometryCollection, feature.geometry)
        transform_geometry_collection(transform_geom, gc)
    else:
        geom = cast(GeojsonGeomNoGeomCollection, feature.geometry)
        transform_geom(geom)
    if feature.bbox is not None:
        feature.bbox = get_bbox(feature)


def init_oas() -> Tuple[dict, str, str, list[MyCrs]]:
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
        crs_identifiers = oas["components"]["schemas"]["crs-enum"]["enum"]
        crs_list = get_projs_axis_info(crs_identifiers)
        crs_param_description = ""
        for crs in crs_list:
            crs_param_description += f"* `{crs.crs_auth_identifier}`: format: `{crs.get_axis_label()}`, dimensions: {crs.nr_of_dimensions}\n"  # ,
        oas["components"]["parameters"]["source-crs"][
            "description"
        ] = f"Source Coordinate Reference System\n{crs_param_description}"
        oas["components"]["parameters"]["target-crs"][
            "description"
        ] = f"Target Coordinate Reference System\n{crs_param_description}"
    api_version = oas["info"]["version"]
    api_title = oas["info"]["title"]
    return (oas, api_title, api_version, crs_list)
