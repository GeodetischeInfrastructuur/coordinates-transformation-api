import csv
import os
from contextlib import contextmanager
from typing import Optional

import pytest
from pyproj import transformer


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
    tfg = transformer.TransformerGroup(
        source_crs, target_crs, allow_ballpark=False, always_xy=True
    )

    if len(tfg.transformers) == 0:
        return (float("inf"), float("inf"), float("inf"), float("inf"))

    return tfg.transformers[0].transform(*coords)


def make_entry(line):
    source = line[0]
    target = line[1]
    coords = tuple(float(num) for num in line[2].strip("()").split(" "))
    return tuple([source, target, coords])


def validation_data():

    test_dir = os.path.dirname(os.path.abspath(__file__))

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
        "EPSG:9289",
        "EPSG:3395",
    ]
    seed_init_crs = "EPSG:7415"
    seed_coord = (0, 400000, 43, 2000)

    file = os.path.join(test_dir, "data", "validation_data.csv")

    if os.path.isfile(file) is True and os.stat(file).st_size != 0:
        with open(os.path.join(test_dir, "data", "validation_data.csv")) as fread:
            t = [make_entry(line) for line in csv.reader(fread, delimiter=",")]
            return t
    else:
        with open(os.path.join(test_dir, "data", "validation_data.csv"), "w") as fwrite:
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

        validation_data()
