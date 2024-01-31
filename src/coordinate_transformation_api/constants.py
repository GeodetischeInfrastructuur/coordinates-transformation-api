DEFAULT_PRECISION = 4 # dit is geen precision (dan zou de standaardafwijking 4 m zijn), maar number of digits. Waarom wordt het aantal decimalen voor graden niet ook gedefinieerd?
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
