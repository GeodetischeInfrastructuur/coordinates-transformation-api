import pytest
from coordinate_transformation_api.crs_transform import get_transform_crs_fun
from coordinate_transformation_api.models import Crs as MyCrs
from coordinate_transformation_api.models import TransformationNotPossibleError
from coordinate_transformation_api.util import str_to_crs

from tests.util import do_pyproj_transformation, nl_saba_validation_data

xy_dim = 2


@pytest.mark.parametrize(
    ("source_crs", "target_crs", "source_coord"), nl_saba_validation_data()
)
def test_transformation(source_crs, target_crs, source_coord):
    source_crs_info = MyCrs.from_crs_str(source_crs)
    target_crs_info = MyCrs.from_crs_str(target_crs)
    unit = target_crs_info.get_x_unit_crs()

    source_crs_crs = str_to_crs(source_crs)
    target_crs_crs = str_to_crs(target_crs)

    if source_crs_info.nr_of_dimensions < target_crs_info.nr_of_dimensions:
        with pytest.raises(
            TransformationNotPossibleError,
            match="number of dimensions source-crs: 2, number of dimensions target-crs: 3",
        ) as e:
            get_transform_crs_fun(source_crs_crs, target_crs_crs)(source_coord)
        assert type(e.value) is TransformationNotPossibleError
    else:
        pyproj_transformed_coord = do_pyproj_transformation(
            source_crs, target_crs, source_coord
        )
        api_transformed_coord = get_transform_crs_fun(
            source_crs_crs,
            target_crs_crs,
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
