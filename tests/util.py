import csv
import os
from contextlib import contextmanager
from importlib import resources
from typing import Optional

import pytest
import yaml
from coordinate_transformation_api import assets
from coordinate_transformation_api.util import uri_to_crs_str
from pyproj import CRS, transformer

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


@contextmanager
def not_raises(exception, message: Optional[str] = ""):
    try:
        yield
    except exception:
        if message != "":
            raise pytest.fail(f"DID RAISE {exception}")  # noqa: B904
        else:
            raise pytest.fail(message.format(exc=exception))  # noqa: B904


def do_pyproj_transformation(
    source_crs: str, target_crs: str, coords: tuple[float, ...]
) -> tuple[float, ...]:

    axis_order = False
    if CRS(source_crs).axis_info[0].abbrev == "Lon":
        axis_order = True

    tfg = transformer.TransformerGroup(
        source_crs, target_crs, allow_ballpark=False, always_xy=axis_order
    )

    if len(tfg.transformers) == 0:
        return (float("inf"), float("inf"), float("inf"), float("inf"))

    return tfg.transformers[0].transform(*coords)


def make_entry(line):
    source = line[0]
    target = line[1]
    coords = tuple(float(num) for num in line[2].strip("()").split(" "))
    return tuple([source, target, coords])


def read_file(file) -> []:
    assets_resources = resources.files(assets)
    seed_crs_list = []

    config_yaml = assets_resources.joinpath("crs/" + file)

    with open(str(config_yaml)) as f:
        config = yaml.safe_load(f)
        uris = config["uri"]
        for uri in uris:
            seed_crs_list.append(uri_to_crs_str(uri))

    return seed_crs_list


def nl_eu_validation_data():
    seed_crs_list = read_file("nl_config.yaml")
    seed_init_crs = "EPSG:7415"
    seed_coord = (100000, 300000, 43, 2000)

    file = os.path.join(TEST_DIR, "data", "nl_validation_data.csv")

    if os.path.isfile(file) is True and os.stat(file).st_size != 0:
        with open(file) as fread:
            t = [make_entry(line) for line in csv.reader(fread, delimiter=",")]
            return t
    else:
        with open(file, "w") as fwrite:
            for source_crs in seed_crs_list:
                for target_crs in seed_crs_list:
                    source_coord = do_pyproj_transformation(
                        seed_init_crs, source_crs, seed_coord
                    )
                    fwrite.write(
                        "{},{},{}\n".format(
                            source_crs,
                            target_crs,
                            "({} {} {} {})".format(*source_coord),
                        )
                    )

        nl_eu_validation_data()


def nl_bonaire_validation_data():

    seed_crs_list = read_file("bonaire_config.yaml")
    seed_init_crs = "NSGI:Bonaire_DPnet_KADpeil"
    seed_coord = (23000.0000, 18000.0000, 10.0000, 2000)

    file = os.path.join(TEST_DIR, "data", "bonaire_validation_data.csv")

    if os.path.isfile(file) is True and os.stat(file).st_size != 0:
        with open(file) as fread:
            t = [make_entry(line) for line in csv.reader(fread, delimiter=",")]
            return t
    else:
        with open(file, "w") as fwrite:
            for source_crs in seed_crs_list:
                for target_crs in seed_crs_list:
                    source_coord = do_pyproj_transformation(
                        seed_init_crs, source_crs, seed_coord
                    )
                    fwrite.write(
                        "{},{},{}\n".format(
                            source_crs,
                            target_crs,
                            "({} {} {} {})".format(*source_coord),
                        )
                    )

        nl_bonaire_validation_data()


def nl_st_eustatius_validation_data():

    seed_crs_list = read_file("st_eustatius_config.yaml")
    seed_init_crs = "NSGI:St_Eustatius_DPnet_Height"
    seed_coord = (502000.0000, 1934000.0000, 100.0000, 2000)

    file = os.path.join(TEST_DIR, "data", "st_eustatius_validation_data.csv")

    if os.path.isfile(file) is True and os.stat(file).st_size != 0:
        with open(file) as fread:
            t = [make_entry(line) for line in csv.reader(fread, delimiter=",")]
            return t
    else:
        with open(file, "w") as fwrite:
            for source_crs in seed_crs_list:
                for target_crs in seed_crs_list:
                    source_coord = do_pyproj_transformation(
                        seed_init_crs, source_crs, seed_coord
                    )
                    fwrite.write(
                        "{},{},{}\n".format(
                            source_crs,
                            target_crs,
                            "({} {} {} {})".format(*source_coord),
                        )
                    )

        nl_st_eustatius_validation_data()


def nl_saba_validation_data():

    seed_crs_list = read_file("saba_config.yaml")
    seed_init_crs = "NSGI:Saba_DPnet_Height"
    seed_coord = (5000.0000, 1000.0000, 300.0000, 2000)

    file = os.path.join(TEST_DIR, "data", "saba_validation_data.csv")

    if os.path.isfile(file) is True and os.stat(file).st_size != 0:
        with open(file) as fread:
            t = [make_entry(line) for line in csv.reader(fread, delimiter=",")]
            return t
    else:
        with open(file, "w") as fwrite:
            for source_crs in seed_crs_list:
                for target_crs in seed_crs_list:
                    source_coord = do_pyproj_transformation(
                        seed_init_crs, source_crs, seed_coord
                    )
                    fwrite.write(
                        "{},{},{}\n".format(
                            source_crs,
                            target_crs,
                            "({} {} {} {})".format(*source_coord),
                        )
                    )

        nl_saba_validation_data()
