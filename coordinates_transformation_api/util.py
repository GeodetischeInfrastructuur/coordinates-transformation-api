from typing import Any, Iterable

from geojson_pydantic import Feature, FeatureCollection
from geojson_pydantic.geometries import (Geometry, GeometryCollection,
                                         _GeometryBase)
from pyproj import CRS, Transformer


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
        def callback(val: list[float]) -> list[float]:
            return [round(x, 6) for x in transformer.transform(*val)]

        geom.coordinates = traverse_geojson_coordinates(
            geom.coordinates, callback=callback
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
