import pytest

from tests.util import (
    _test_transformation,
    nl_bonaire_validation_data,
    nl_eu_validation_data,
    nl_saba_validation_data,
    nl_st_eustatius_validation_data,
)


@pytest.mark.parametrize(("source_crs", "target_crs", "source_coord"), nl_bonaire_validation_data())
def test_transformations_bonaire(source_crs, target_crs, source_coord):
    _test_transformation(source_crs, target_crs, source_coord)


@pytest.mark.parametrize(("source_crs", "target_crs", "source_coord"), nl_eu_validation_data())
def test_transformations_nl_eu(source_crs, target_crs, source_coord):
    _test_transformation(source_crs, target_crs, source_coord)


@pytest.mark.parametrize(("source_crs", "target_crs", "source_coord"), nl_saba_validation_data())
def test_transformations_nl_saba(source_crs, target_crs, source_coord):
    _test_transformation(source_crs, target_crs, source_coord)


@pytest.mark.parametrize(("source_crs", "target_crs", "source_coord"), nl_st_eustatius_validation_data())
def test_transformations_nl_st_eustatius(source_crs, target_crs, source_coord):
    _test_transformation(source_crs, target_crs, source_coord)
