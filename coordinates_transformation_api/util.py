from pyproj import CRS


def get_projs_axis_info(proj_strings):
    result = {}
    for proj_string in proj_strings:
        crs = CRS.from_authority(*proj_string.split(":"))
        nr_dim = len(crs.axis_info)
        axis_labels = list(map(lambda x: f"{x.abbrev} ({x.unit_name})", crs.axis_info))
        axis_info_summary = {"dimensions": nr_dim, "axis_labels": axis_labels}
        result[proj_string] = axis_info_summary
    return result


def transform_geom(transformer, geom):
    match geom.type:
        case "Point":
            geom.coordinates = transform_point(transformer, geom)
        case "MultiPoint":
            geom.coordinates = transform_multipoint_linestring(transformer, geom)
        case "LineString":
            geom.coordinates = transform_multipoint_linestring(transformer, geom)
        case "MultiLineString":
            geom.coordinates = transform_polygon_multilinestring(transformer, geom)
        case "Polygon":
            geom.coordinates = transform_polygon_multilinestring(transformer, geom)
        case "MultiPolygon":
            geom.coordinates = transform_multipolygon(transformer, geom)
    return geom


def transform_multipolygon(transformer, geom):
    new_coords = []
    for polygon in geom.coordinates:
        new_polygon = []
        for ring in polygon:
            zipped_transformed_coords = transformer.transform(*zip(*ring))
            new_polygon.append(list(zip(*zipped_transformed_coords)))
        new_coords.append(new_polygon)
    return new_coords


def transform_polygon_multilinestring(transformer, geom):
    new_coords = []
    for ring_linestring in geom.coordinates:
        zipped_transformed_coords = transformer.transform(*zip(*ring_linestring))
        new_coords.append(list(zip(*zipped_transformed_coords)))
    return new_coords


def transform_multipoint_linestring(transformer, geom):
    geom.coordinates = list(transformer.transform(*geom.coordinates))
    zipped_transformed_coords = transformer.transform(*zip(*geom.coordinates))
    new_coords = list(zip(*zipped_transformed_coords))
    return new_coords


def transform_point(transformer, geom):
    return list(transformer.transform(*geom.coordinates))
