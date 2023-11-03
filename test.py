from collections import Counter


def merge_geometry_collections_shapelyfication(input_shp_geoms: list) -> list:
    indices = list(map(lambda x: x["index"][0], input_shp_geoms))
    counter = Counter(indices)
    geom_coll_indices = [x for x in counter if counter[x] > 1]
    output_shp_geoms = list(
        filter(lambda x: x["index"][0] not in geom_coll_indices, input_shp_geoms)
    )
    for i in geom_coll_indices:
        geom_collection_geoms = list(
            filter(lambda x: x["index"][0] == i, input_shp_geoms)
        )
        output_shp_geoms.append(
            [geom_collection_geoms]
        )  # TODO: creatE GEOMETRYCOLLECTIO
    return output_shp_geoms


input = [
    {"result": "FOO", "index": [0, 0]},
    {"result": "BAR", "index": [0, 1]},
    {"result": "BAR", "index": [2]},
    {"result": "BAR", "index": [3]},
    {"result": "BAR", "index": [0, 2]},
]
res = merge_geometry_collections_shapelyfication(input)
print(res)
