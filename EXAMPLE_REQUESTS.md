## Example operations

> **TODO:** Clean up example operations/API calls and add documentation

```bash
# Landingpage
curl "https://api.nsgi.nl/coordinatestransformation/v2/"
# Conformance
curl "https://api.nsgi.nl/coordinatestransformation/v2/conformance"
# OAS 3.0 Spec
curl "https://api.nsgi.nl/coordinatestransformation/v2/openapi"
```

```bash
# Transformation with GET operation
# Inputs through query parameters will return a GeoJSON respons
curl "https://api.nsgi.nl/coordinatestransformation/v2/transform?f=json&source-csr=EPSG:7415&target-crs=EPSG:7931&coordinates=194174.00,465887.33,42.1"
```

```bash
# Transformation with POST operation
# Input as POST body will return the same (if supported) object type.
# In this case GeoJSON as input will return GeoJSON as output
curl --request POST 'https://api.nsgi.nl/coordinatestransformation/v2/transform?f=json&source-csr=EPSG:7415&target-crs=EPSG:7931'
--header 'Content-Type: application/geo+json'
--data-raw '{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [194174.00, 465887.33]
  },
  "properties": {
    "name": "de Brug"
  }
}'
```

```bash
# Transformatie with POST operation
# In this case CityJSON as input will return CityJSON as output
curl --request POST 'https://api.nsgi.nl/coordinatestransformation/v2/source-csr=EPSG:7415&target-crs=EPSG:7931'
--header 'Content-Type: application/city+json'
--data-raw '{
  "type": "CityJSON",
  "version": "1.1",
  "transform": {
    "scale": [1.0, 1.0, 1.0],
    "translate": [0.0, 0.0, 0.0]
  },
  "CityObjects": {},
  "vertices": []
}'
```

```bash
# The source-crs is optional with POST operations, but if not present then it should be defined in the object.
curl --request POST 'http://api.nsgi.nl/coordinatestransformation/v2?f=json&target-crs=EPSG:7931'
--header 'Content-Type: application/city+json'
--data-raw '{
  "type": "CityJSON",
  "version": "1.1",
  "transform": {
    "scale": [1.0, 1.0, 1.0],
    "translate": [0.0, 0.0, 0.0]
  },
  "metadata": {
    "referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/7415"
  },
  "CityObjects": {},
  "vertices": []
}'
```

--- 

```sh
curl -X 'POST' 'http://localhost:8000/transform?source-crs=EPSG:28992&target-crs=EPSG:4326' -H 'Content-Type: application/json' -d @feature-geometry-collection.json
```


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
curl -X 'POST' 'http://localhost:8000/transform?target-crs=EPSG:4326' \
  -H 'Content-Type: application/json' \
  -d @tests/data/geometry.json
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
