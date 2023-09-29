from typing import Callable, Union, cast

from pyproj import CRS, Transformer

# note get_transform_callback is in it's own file to prevent cyclical import between cityjson.py and util.py
# since cityjson.py requires get_transform_callback and util.py requires  CityJsonV113 from cityjson.py


def get_transformer(source_crs: str, target_crs: str) -> Transformer:
    source_crs_crs = CRS.from_authority(*source_crs.split(":"))
    target_crs_crs = CRS.from_authority(*target_crs.split(":"))
    return Transformer.from_crs(source_crs_crs, target_crs_crs, always_xy=True)


def get_transform_callback(
    source_crs: str, target_crs: str, precision: int | None = None
) -> Callable[
    [Union[tuple[float, float], tuple[float, float, float], list[float]]],
    tuple[float, ...],
]:
    """TODO: improve type annotation/handling geojson/cityjson transformation, with the current implementation mypy is not complaining"""

    def my_round(val: float, precision: int | None) -> float | int:
        if precision is None:
            return val
        else:
            return round(val, precision)

    def callback(
        val: Union[tuple[float, float], tuple[float, float, float], list[float]]
    ) -> tuple[float, ...]:
        transformer = get_transformer(source_crs, target_crs)

        if transformer.target_crs is None:
            raise ValueError("transformer.target_crs is None")
        dim = len(transformer.target_crs.axis_info)
        two_dim = 2
        three_dim = 3
        if (
            dim is not None and dim != len(val) and (two_dim > dim > three_dim)
        ):  # check so we can safely cast to Tuple[float, float], Tuple[float, float, float]
            raise ValueError(
                f"number of dimensions of target-crs should be 2 or 3, is {dim}"
            )
        val = cast(Union[tuple[float, float], tuple[float, float, float]], val[0:dim])

        # GeoJSON and CityJSON by definition has coordinates always in lon-lat-height (or x-y-z) order. Transformer has been created with `always_xy=True`,
        # to ensure input and output coordinates are in in lon-lat-height (or x-y-z) order.
        return tuple(
            [float(my_round(x, precision)) for x in transformer.transform(*val)]
        )

    return callback
