from collections import Counter
from collections.abc import Generator
from itertools import chain
from typing import Any, Callable, cast

from geodense.geojson import CrsFeatureCollection
from geodense.lib import (  # type: ignore  # type: ignore
    THREE_DIMENSIONAL,
    TWO_DIMENSIONAL,
    GeojsonObject,
    apply_function_on_geojson_geometries,
)
from geodense.types import GeojsonGeomNoGeomCollection
from geojson_pydantic import Feature, GeometryCollection
from geojson_pydantic.geometries import _GeometryBase
from geojson_pydantic.types import BBox
from pyproj import CRS, Transformer
from shapely import GeometryCollection as ShpGeometryCollection
from shapely.geometry import shape

from coordinate_transformation_api.constants import DEFAULT_PRECISION
from coordinate_transformation_api.models import Crs as MyCrs
from coordinate_transformation_api.types import CoordinatesType


def get_precision(target_crs_crs: MyCrs) -> int:
    unit = target_crs_crs.get_x_unit_crs()
    if unit == "degree":
        return DEFAULT_PRECISION + 5
    return DEFAULT_PRECISION


def get_shapely_objects(
    body: GeojsonObject,
) -> list[Any]:
    def merge_geometry_collections_shapelyfication(input_shp_geoms: list) -> list:
        indices = list(
            map(
                lambda x: x["index"][0] if hasattr(x, "index") else None,
                input_shp_geoms,
            )
        )
        counter = Counter(indices)
        geom_coll_indices = [x for x in counter if counter[x] > 1]
        output_shp_geoms = [
            x["result"]
            for x in input_shp_geoms
            if not hasattr(x, "index") or x["index"][0] not in geom_coll_indices
        ]
        for i in geom_coll_indices:
            geom_collection_geoms = [
                x["result"] for x in input_shp_geoms if x["index"][0] == i
            ]
            output_shp_geoms.append(ShpGeometryCollection(geom_collection_geoms))
        return output_shp_geoms

    transform_fun = get_shapely_object_fun()
    result = apply_function_on_geojson_geometries(body, transform_fun)
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


def get_update_geometry_bbox_fun() -> Callable:
    def update_bbox(
        geometry: GeojsonGeomNoGeomCollection,
        _result: list,
        _indices: list[int] | None = None,
    ) -> None:
        coordinates = get_coordinate_from_geometry(geometry)
        geometry.bbox = get_bbox_from_coordinates(coordinates)

    return update_bbox


def get_crs_transform_fun(
    source_crs: str, target_crs: str, epoch: float | None = None
) -> Callable:
    target_crs_crs: MyCrs = MyCrs.from_crs_str(target_crs)
    precision = get_precision(target_crs_crs)

    def my_fun(
        geom: GeojsonGeomNoGeomCollection,
        _result: list,
        _indices: list[int] | None = None,
    ) -> (
        None
    ):  # add _result, _indices args since required by transform_geometries_req_body
        callback = get_transform_crs_fun(source_crs, target_crs, precision, epoch=epoch)
        geom.coordinates = traverse_geojson_coordinates(
            cast(list[list[Any]] | list[float] | list[int], geom.coordinates),
            callback=callback,
        )

    return my_fun


def get_validate_json_coords_fun() -> Callable:
    def validate_json_coords(
        geometry: GeojsonGeomNoGeomCollection,
        result: list,
        _indices: list[int] | None = None,
    ) -> None:
        def coords_has_inf(coordinates: Any) -> bool:  # noqa: ANN401
            gen = (
                x
                for x in explode(coordinates)
                if abs(x[0]) == float("inf") or abs(x[1]) == float("inf")
            )
            return next(gen, None) is not None

        coords = get_coordinate_from_geometry(geometry)
        result.append(coords_has_inf(coords))
        # TODO: HANDLE result in calling code
        # if coords_has_inf(coordinates):
        #     raise_response_validation_error(
        #         "Out of range float values are not JSON compliant", ["responseBody"]
        #     )

    return validate_json_coords


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
    return list(
        chain(explode(geom.coordinates))
    )  # TODO: check if chain(list()) is required...


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


def get_transformer(source_crs: str, target_crs: str) -> Transformer:
    source_crs_crs = CRS.from_authority(*source_crs.split(":"))
    target_crs_crs = CRS.from_authority(*target_crs.split(":"))
    return Transformer.from_crs(source_crs_crs, target_crs_crs, always_xy=True)


def get_transform_crs_fun(
    source_crs: str,
    target_crs: str,
    precision: int | None = None,
    epoch: float | None = None,
) -> Callable[[CoordinatesType], tuple[float, ...],]:
    """TODO: improve type annotation/handling geojson/cityjson transformation, with the current implementation mypy is not complaining"""

    transformer = get_transformer(source_crs, target_crs)

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
        input = tuple([*val, float(epoch) if epoch is not None else None])

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
