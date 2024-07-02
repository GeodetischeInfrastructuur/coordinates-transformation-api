import pytest
from coordinate_transformation_api.util import uri_to_crs_str


@pytest.mark.parametrize(
    ("uri", "expectation"),
    [
        ("http://www.nsgi.nl/def/crs/NSGI/0/Saba_DPnet", "NSGI:Saba_DPnet"),
        (
            "http://www.nsgi.nl/def/crs/NSGI/0/Saba_DPnet_Height",
            "NSGI:Saba_DPnet_Height",
        ),
        (
            "http://www.nsgi.nl/def/crs/NSGI/0/Saba2020_GEOGRAPHIC_2D",
            "NSGI:Saba2020_GEOGRAPHIC_2D",
        ),
        (
            "http://www.nsgi.nl/def/crs/NSGI/0/Saba2020_GEOGRAPHIC_3D",
            "NSGI:Saba2020_GEOGRAPHIC_3D",
        ),
        (
            "http://www.nsgi.nl/def/crs/NSGI/0/Saba2020_GEOCENTRIC",
            "NSGI:Saba2020_GEOCENTRIC",
        ),
        ("http://www.opengis.net/def/crs/EPSG/0/32619", "EPSG:32619"),
        ("http://www.opengis.net/def/crs/EPSG/0/32620", "EPSG:32620"),
        ("http://www.opengis.net/def/crs/EPSG/0/9000", "EPSG:9000"),
        ("http://www.opengis.net/def/crs/EPSG/0/4326", "EPSG:4326"),
        ("http://www.opengis.net/def/crs/OGC/0/CRS84", "OGC:CRS84"),
        ("http://www.opengis.net/def/crs/EPSG/0/7912", "EPSG:7912"),
        ("http://www.opengis.net/def/crs/EPSG/0/4979", "EPSG:4979"),
        ("http://www.opengis.net/def/crs/OGC/0/CRS84h", "OGC:CRS84h"),
        ("http://www.opengis.net/def/crs/EPSG/0/7789", "EPSG:7789"),
    ],
)
def test_get_precision(uri, expectation):
    result = uri_to_crs_str(uri)

    assert expectation == result
