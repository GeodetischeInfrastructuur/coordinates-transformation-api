import pytest
from coordinate_transformation_api.crs_transform import get_transform_crs_fun
from coordinate_transformation_api.models import Crs as MyCrs
from pyproj import transformer

seed_crs_list = [
    "EPSG:7415",
    "EPSG:28992",
    "EPSG:4258",
    "EPSG:3035",
    "EPSG:3034",
    "EPSG:3043",
    "EPSG:3044",
    "EPSG:9067",
    "OGC:CRS84",
    "EPSG:4326",
    "EPSG:3857",
    "EPSG:32631",
    "EPSG:32632",
    "EPSG:9000",
    "EPSG:9755",
    "EPSG:4937",
    "EPSG:4936",
    "EPSG:9286",
    "EPSG:7931",
    "EPSG:7930",
    "OGC:CRS84h",
    "EPSG:4979",
    "EPSG:7912",
    "EPSG:7789",
    "EPSG:9754",
    "EPSG:9753",
]
seed_init_crs = "EPSG:7415"
seed_coord = (100000, 300000, 43, 2000)


def do_pyproj_transformation(
    source_crs: str, target_crs: str, coords: tuple[float, ...]
) -> tuple[float, ...]:
    tfg = transformer.TransformerGroup(
        source_crs, target_crs, allow_ballpark=False, always_xy=True
    )

    if len(tfg.transformers) == 0:
        return (float("inf"), float("inf"), float("inf"), float("inf"))

    return tfg.transformers[0].transform(*coords)


def get_test_data() -> tuple[str, str, tuple[float, ...]]:

    test_data = []

    for source_crs in seed_crs_list:
        for target_crs in seed_crs_list:
            source_coord = do_pyproj_transformation(
                seed_init_crs, target_crs, seed_coord
            )
            test_data.append((source_crs, target_crs, source_coord))

    return test_data


@pytest.mark.parametrize("source_crs", "target_crs", "source_coord", get_test_data())
def test_transformation(source_crs, target_crs, source_coord):

    source_crs_info = MyCrs.from_crs_str(source_crs)
    target_crs_info = MyCrs.from_crs_str(target_crs)
    unit = target_crs_info.get_x_unit_crs()

    if source_crs_info.nr_of_dimensions < target_crs_info.nr_of_dimensions:
        with pytest.raises(Exception, match="ValueError") as e:
            get_transform_crs_fun(source_crs, target_crs)(source_coord)
        assert type(e.value.__cause__) is ValueError
    else:
        api_transformed_coord = get_transform_crs_fun(
            source_crs,
            target_crs,
            precision=(4 if unit == "metre" else 9),
            epoch=source_coord[3],
        )(source_coord[0:3])
        pyproj_transformed_coord = do_pyproj_transformation(
            source_crs, target_crs, source_coord
        )

        if unit == "metre":
            pyproj_transformed_coord = (
                round(pyproj_transformed_coord[0], 4),
                round(pyproj_transformed_coord[1], 4),
                round(pyproj_transformed_coord[2], 4),
            )
        else:
            pyproj_transformed_coord = (
                round(pyproj_transformed_coord[0], 9),
                round(pyproj_transformed_coord[1], 9),
                round(pyproj_transformed_coord[2], 4),
            )

        pyproj_transformed_coord = (
            pyproj_transformed_coord[0],
            pyproj_transformed_coord[1],
            round(pyproj_transformed_coord[2], 4),
        )  # round height
        assert (
            api_transformed_coord[0 : target_crs_info.nr_of_dimensions]
            == pyproj_transformed_coord[0 : target_crs_info.nr_of_dimensions]
        )
