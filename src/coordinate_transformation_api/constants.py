DEFAULT_DIGITS_FOR_ROUNDING = 4
HEIGHT_DIGITS_FOR_ROUNDING = (
    4  # height will always be in metres, therefor fixed precision of 4 decimals
)
DENSIFY_CRS_2D = "EPSG:9067"
DENSIFY_CRS_3D = "EPSG:7931"
DEVIATION_VALID_BBOX = [
    2.0,
    50.0,
    8.0,
    56.0,
]  # bbox of RD and NAP GeoTIFF grids in epsg:9067 - area valid for doing density check (based on deviation param)
DENSITY_CHECK_RESULT_HEADER = "density-check-result"
THREE_DIMENSIONAL = 3
TWO_DIMENSIONAL = 2
