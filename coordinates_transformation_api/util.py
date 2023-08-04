from pyproj import CRS


def get_projs_axis_info(proj_strings):
    result = {}
    for proj_string in proj_strings:
        proj_string_split = proj_string.split(":")
        if proj_string_split[0] != "EPSG":
            raise ValueError(
                f"Expecteded EPSG proj string like `EPSG:XXXX`, but received {proj_string}"
            )
        crs = CRS.from_epsg(proj_string_split[1])
        nr_dim = len(crs.axis_info)
        axis_labels = list(map(lambda x: f"{x.abbrev} ({x.unit_name})", crs.axis_info))
        axis_info_summary = {"dimensions": nr_dim, "axis_labels": axis_labels}
        result[proj_string] = axis_info_summary
    return result
