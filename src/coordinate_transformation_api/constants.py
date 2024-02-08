DEFAULT_DIGITS_FOR_ROUNDING = 4
HEIGHT_DIGITS_FOR_ROUNDING = (
    4  # height will always be in metres, therefor fixed precision of 4 decimals
)
DENSIFY_CRS_2D = "EPSG:9067"
DENSIFY_CRS_3D = "EPSG:7931"
DEVIATION_VALID_BBOX = [
    3.1201,
    50.2191,
    7.5696,
    54.1238,
]  # bbox in epsg:4258 - area valid for doing density check (based on deviation param)
DENSITY_CHECK_RESULT_HEADER = "density-check-result"
THREE_DIMENSIONAL = 3
TWO_DIMENSIONAL = 2
