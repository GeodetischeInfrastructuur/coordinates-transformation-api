# EXAMPLES

```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=EPSG%3A28992&target-crs=EPSG%3A28992' \
  -H 'Content-Type: application/json' \
  -d '{"type":"Feature","crs":"foo","properties": {},"geometry":{"type":"Point","coordinates":[633092.3577539952,6849959.336556375]}}' | jq
```

```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=EPSG%3A3857&target-crs=EPSG%3A28992' \
  -H 'Content-Type: application/json' \
  -d '{"type":"Feature","properties": {},"geometry":{"type":"Point","coordinates":[633092.3577539952,6849959.336556375]},"crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::3857"}}}' | jq
```

```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=EPSG%3A28992&target-crs=EPSG%3A4326' \
  -H 'Content-Type: application/json' \
  -d '{"type":"Feature","properties": {},"geometry":{"type":"MultiPoint","coordinates":[[160000,455000],[160100,455000]]
}}' | jq
```

```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=EPSG%3A28992&target-crs=EPSG%3A4326' \
  -H 'Content-Type: application/json' \
  -d '{"type":"Feature","properties": {},"geometry":{"type":"MultiLineString","coordinates":[[[170000,455000],[170100,455000]],[[160000,455000],[160100,455000]]]
}}' | jq
```

```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=EPSG%3A4326&target-crs=EPSG%3A3857' \
  -H 'Content-Type: application/json' \
  -d '{ "type": "Feature", "properties": { "name": "Parc de la Colline" }, "geometry": { "type": "MultiPolygon", "coordinates": [ [ [ [ -72.357206347890767, 47.72858763003908 ], [ -71.86027854004486, 47.527648291638172 ], [ -72.37075892446839, 47.539848426151735 ], [ -72.357206347890767, 47.72858763003908 ] ] ],  [ [ [ -72.357206347890767, 47.72858763003908 ], [ -71.86027854004486, 47.527648291638172 ], [ -72.37075892446839, 47.539848426151735 ], [ -72.357206347890767, 47.72858763003908 ] ] ]] } }' |  jq
```

```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=OGC:CRS84&target-crs=EPSG:4326' \
  -H 'Content-Type: application/json' \
  -d @example/polygon.json
```



```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=OGC:CRS84&target-crs=EPSG:28992' \
  -H 'Content-Type: application/json' \
  -d '{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature", 
    "properties": {},
    "geometry": { 
      "type": "GeometryCollection",
      "geometries": [ 
        { 
          "type": "Point",
          "coordinates": [
            61.34765625,
            48.63290858589535
          ]
        },
        {
          "type": "Polygon",
          "coordinates": [
            [
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ]
            ]
          ]
        }
      ]
    }
  }]
}'  | jq
```



```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=OGC:CRS84&target-crs=EPSG:28992' \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "Feature", 
    "properties": {},
    "geometry": { 
      "type": "GeometryCollection",
      "geometries": [ 
        { 
          "type": "Point",
          "coordinates": [
            61.34765625,
            48.63290858589535
          ]
        },
        {
          "type": "Polygon",
          "coordinates": [
            [
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ]
            ]
          ]
        }
      ]
    }
  }' | jq
```


```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=OGC:CRS84&target-crs=EPSG:28992' \
  -H 'Content-Type: application/json' \
  -d '{ 
      "type": "GeometryCollection",
      "geometries": [ 
        { 
          "type": "Point",
          "coordinates": [
            61.34765625,
            48.63290858589535
          ]
        },
        {
          "type": "Polygon",
          "coordinates": [
            [
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ],
              [
                59.94140624999999,
                50.65294336725709
              ]
            ]
          ]
        }
      ]
    }' | jq
  ```
