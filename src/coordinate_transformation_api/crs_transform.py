from collections.abc import Generator
from importlib import resources as impresources
from itertools import chain
from typing import Any, Callable, cast

import yaml
from geodense.geojson import CrsFeatureCollection
from geodense.lib import (  # type: ignore  # type: ignore
    GeojsonObject,
    apply_function_on_geojson_geometries,
)
from geodense.types import GeojsonCoordinates, GeojsonGeomNoGeomCollection
from geojson_pydantic import Feature, GeometryCollection
from geojson_pydantic.geometries import _GeometryBase
from geojson_pydantic.types import BBox
from pyproj import CRS, Transformer, transformer
from shapely import GeometryCollection as ShpGeometryCollection
from shapely.geometry import shape

from coordinate_transformation_api import assets
from coordinate_transformation_api.constants import (
    DEFAULT_PRECISION,
    THREE_DIMENSIONAL,
    TWO_DIMENSIONAL,
)
from coordinate_transformation_api.models import Crs as MyCrs
from coordinate_transformation_api.models import TransformationNotPossibleError
from coordinate_transformation_api.types import CoordinatesType, ShapelyGeometry

assets_resources = impresources.files(assets)
api_conf = assets_resources.joinpath("config.yaml")
with open(str(api_conf)) as f:
    CRS_CONFIG = yaml.safe_load(f)


def get_precision(target_crs_crs: MyCrs) -> int:
    unit = target_crs_crs.get_x_unit_crs()
    if unit == "degree":
        return DEFAULT_PRECISION + 5
    return DEFAULT_PRECISION


def get_shapely_objects(
    body: GeojsonObject,
) -> list[ShapelyGeometry]:
    transform_fun = get_shapely_object_fun()
    result = apply_function_on_geojson_geometries(body, transform_fun)
    flat_result: list[ShapelyGeometry] = []
    for item in result:
        if isinstance(item, list):
            flat_result.append(ShpGeometryCollection(item))
        else:
            flat_result.append(item)
    return flat_result


def get_shapely_object_fun() -> Callable:
    def shapely_object(geometry: GeojsonGeomNoGeomCollection) -> ShapelyGeometry:
        return shape(geometry)

    return shapely_object


def get_crs_transform_fun(
    source_crs: str, target_crs: str, epoch: float | None = None
) -> Callable:
    target_crs_crs: MyCrs = MyCrs.from_crs_str(target_crs)
    precision = get_precision(target_crs_crs)

    def my_fun(
        geom: GeojsonGeomNoGeomCollection,
    ) -> GeojsonCoordinates:
        callback = get_transform_crs_fun(source_crs, target_crs, precision, epoch=epoch)
        geom.coordinates = traverse_geojson_coordinates(
            cast(list[list[Any]] | list[float] | list[int], geom.coordinates),
            callback=callback,
        )
        return geom.coordinates

    return my_fun


def get_json_coords_contains_inf_fun() -> Callable[[GeojsonGeomNoGeomCollection], bool]:
    def json_coords_contains_inf(
        geometry: GeojsonGeomNoGeomCollection,
    ) -> bool:
        coordinates = get_coordinate_from_geometry(geometry)
        gen = (
            x
            for x in explode(coordinates)
            if abs(x[0]) == float("inf") or abs(x[1]) == float("inf")
        )
        return next(gen, None) is not None

    return json_coords_contains_inf


def update_bbox_geojson_object(  # noqa: C901
    geojson_obj: GeojsonObject,
) -> None:
    def rec_fun(  # noqa: C901
        geojson_obj: GeojsonObject,
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
            geom_coords: list = get_coordinate_from_geometry(geojson_obj)
            if geojson_obj.bbox is not None:
                geojson_obj.bbox = get_bbox_from_coordinates(geom_coords)
            return geom_coords
        else:
            raise ValueError(
                f"received unexpected type in geojson_obj var: {type(geojson_obj)}"
            )

    _ = rec_fun(geojson_obj)


def traverse_geojson_coordinates(
    geojson_coordinates: list[list] | list[float] | list[int],
    callback: Callable[
        [CoordinatesType],
        tuple[float, ...],
    ],
) -> Any:  # noqa: ANN401
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


def get_coordinate_from_geometry(
    item: _GeometryBase,
) -> list:
    geom = cast(_GeometryBase, item)
    return list(chain(explode(geom.coordinates)))


def explode(coords: Any) -> Generator[Any, Any, None]:  # noqa: ANN401
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


def get_bbox_from_coordinates(coordinates: Any) -> BBox:  # noqa: ANN401
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


def exclude_transformation(source_crs_str: str, target_crs_str: str) -> bool:
    if source_crs_str in CRS_CONFIG and (
        target_crs_str in CRS_CONFIG[source_crs_str]["exclude-transformations"]
    ):
        return True
    return False


def needs_epoch(tf: Transformer) -> bool:
    # Currently the time dependent & specific operation method code are hardcoded
    # These are extracted from the 'coordinate_operation_method' table in the proj.db
    #
    static_coordinate_operation_methode_time_dependent = [
        "1053",
        "1054",
        "1056",
        "1057",
    ]
    static_coordinate_operation_methode_time_specific = ["1065", "1066"]
    time_coordinate_operation_methodes = (
        static_coordinate_operation_methode_time_dependent
        + static_coordinate_operation_methode_time_specific
    )

    has_epoch = False

    if (
        tf.target_crs is not None
        and tf.target_crs.datum is not None
        and tf.target_crs.datum.type_name == "Dynamic Geodetic Reference Frame"
    ):
        has_epoch = True

    if tf.operations is not None:
        for operation in tf.operations:
            if (
                operation.type_name == "Transformation"
                and operation.method_code in time_coordinate_operation_methodes
            ):
                has_epoch = True

    return has_epoch


def get_transformer(
    source_crs: str, target_crs: str, epoch: float | None
) -> Transformer:  # quit
    s_crs = CRS.from_authority(*source_crs.split(":"))
    t_crs = CRS.from_authority(*target_crs.split(":"))

    if len(s_crs.axis_info) < len(t_crs.axis_info):
        raise TransformationNotPossibleError(
            src_crs=str(s_crs),
            target_crs=str(t_crs),
            reason=f"number of dimensions source-crs: {len(s_crs.axis_info)}, number of dimensions target-crs: {len(t_crs.axis_info)}",
        )

    if exclude_transformation(source_crs, target_crs):
        raise TransformationNotPossibleError(source_crs, target_crs)

    # Area of interest spanning NL
    # coord from EPSG.org Netherlands - onshore
    aoi = transformer.AreaOfInterest(3.2, 50.75, 7.22, 53.7)

    # Get available transformer through TransformerGroup
    # TODO check/validate if always_xy=True is correct
    tfg = transformer.TransformerGroup(
        s_crs, t_crs, allow_ballpark=False, always_xy=True, area_of_interest=aoi
    )

    # If everything is 'right' we should always have a transformer
    # based on our configured proj.db. Therefor this error.
    if len(tfg.transformers) == 0:
        raise TransformationNotPossibleError(
            src_crs=str(s_crs),
            target_crs=str(t_crs),
        )

    # When no input epoch is given we need to check that we don't perform an time dependent transformation. If we do
    # the transformation will be done with a default epoch value, which isn't correct. So we need to search for the "best"
    # transformation that doesn't include a time dependent operation methode.
    if epoch is None:
        for tf in tfg.transformers:
            if needs_epoch(tf) is not True:
                return tf

    # Select 1st result. The first result is based on the input parameters the "best" result
    return tfg.transformers[0]


def get_transform_crs_fun(  #
    source_crs: str,
    target_crs: str,
    precision: int | None = None,
    epoch: float | None = None,
) -> Callable[[CoordinatesType], tuple[float, ...],]:
    """TODO: improve type annotation/handling geojson/cityjson transformation, with the current implementation mypy is not complaining"""

    transformer = get_transformer(source_crs, target_crs, epoch)

    def my_round(val: float, precision: int | None) -> float | int:
        if precision is None:
            return val
        else:
            return round(val, precision)

    def transform_crs(val: CoordinatesType) -> tuple[float, ...]:
        if transformer.target_crs is None:
            raise ValueError("transformer.target_crs is None")
        dim = len(transformer.target_crs.axis_info)
        if (
            dim is not None
            and dim != len(val)
            and TWO_DIMENSIONAL > dim > THREE_DIMENSIONAL
        ):
            # check so we can safely cast to tuple[float, float], tuple[float, float, float]
            raise ValueError(
                f"number of dimensions of target-crs should be 2 or 3, is {dim}"
            )
        val = cast(tuple[float, float] | tuple[float, float, float], val[0:dim])
        # TODO: fix epoch handling, should only be added in certain cases
        # when one of the src or tgt crs has a dynamic time component
        # or the transformation used has a datetime component
        # for now simple check on coords length (which is not correct)
        input = tuple(
            [
                *val,
                float(epoch)
                if len(val) == THREE_DIMENSIONAL and epoch is not None
                else None,
            ]
        )

        # GeoJSON and CityJSON by definition has coordinates always in lon-lat-height (or x-y-z) order. Transformer has been created with `always_xy=True`,
        # to ensure input and output coordinates are in in lon-lat-height (or x-y-z) order.
        # Regarding the epoch: this is stripped from the result of the transformer. It's used as a input parameter for the transformation but is not
        # 'needed' in the result, because there is no conversion of time, e.i. a epoch value of 2010.0 will stay 2010.0 in the result. Therefor the result
        # of the transformer is 'stripped' with [0:dim]
        return tuple(
            [
                float(my_round(x, precision))
                for x in transformer.transform(*input)[0:dim]
            ]
        )

    return transform_crs
