import pytest

from coordinate_transformation_api.crs_transform import get_transform_crs_fun
from coordinate_transformation_api.models import TransformationNotPossibleError
from coordinate_transformation_api.util import str_to_crs
from tests.util import do_pyproj_transformation, nl_eu_validation_data

xy_dim = 2


@pytest.mark.parametrize(
    ("source_crs", "target_crs", "source_coord"), nl_eu_validation_data()
)
def test_transformation(source_crs, target_crs, source_coord):
    s_crs = str_to_crs(source_crs)
    t_crs = str_to_crs(target_crs)

    unit = t_crs.axis_info[0].unit_name

    if len(s_crs.axis_info) < len(t_crs.axis_info):
        with pytest.raises(
            TransformationNotPossibleError,
            match="number of dimensions source-crs: 2, number of dimensions target-crs: 3",
        ) as e:
            get_transform_crs_fun(s_crs, t_crs)(source_coord)
        assert type(e.value) is TransformationNotPossibleError
    elif source_crs == "EPSG:9289" or target_crs == "EPSG:9289":
        # skip ETRS89 + LAT NL depth
        assert True
    else:
        pyproj_transformed_coord = do_pyproj_transformation(
            source_crs, target_crs, source_coord
        )
        api_transformed_coord = get_transform_crs_fun(
            s_crs,
            t_crs,
            precision=(4 if unit == "metre" else 9),
            epoch=source_coord[3],
        )(source_coord[0:3])
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
        assert api_transformed_coord[0:2] == pyproj_transformed_coord[0:2]

        if (
            len(api_transformed_coord) > xy_dim
            and len(pyproj_transformed_coord) > xy_dim
        ):
            assert api_transformed_coord[2] == pytest.approx(
                pyproj_transformed_coord[2], 0.0001
            )
