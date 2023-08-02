# Coordinatetransfomation API

RESTful API implementation on the OSGEO PROJ applications projinfo and cs2cs.

## Assumptions

- API in Engels
- Easily accessible, but correct
- Conform the OGC API Commen and the NL API Design rules.

## ToDo

The actions that need to be executed are primarily based on the recommandations
of the [OGC API Common](./OGC-API-Common.md) spec and the [NL API](./NL-API.md)
Design rues. Examples of these are:

- No trailing slash `../`.
- API-Version header in responses.
- Resource limits on:
    + max size attr
    + max features
    + max coordinates
    + max runtime
- Additional error messages
- Changelog publishing on github.com/GeodetischeInfrastuctuur
- Allow with POST operatie the crs in the (geo)json, when there is no source-crs
  parameter.
    + with additional scenarios for other combinations.

## Develop

To install from source requires minimum version of pip: `23.2.1`.

Install dev dependencies with:

```sh
pip install ".[dev]"
```

Install enable precommit hook with:

```sh
git config -f .gitconfig core.hooksPath .githooks
```

## Install

```bash
pip3 install .
```

## Run

```bash
ct-api
```

## Example operaties

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

## URL

The URL of the current API is <https://api.transformation.nsgi.nl/v1>. Most
straight forward approach would be to publish the new API with
<https://api.transformation.nsgi.nl/v2>. This how ever poses a couple of issues:

1. Currently the endpoint in use is done through the API Gateway that's
   configured on the internal infrastructure. The plan with the new API is that
   this will run on Azure. It is not possible to share a (sub)domain between two
   infrastructures, without additional components or proxying.
1. The name `transformatie` is to abstract and should be
   `coordinatestransformation` for better identification of what the API does.

Given these points a URL for the API like
<https://api.nsgi.nl/coordinatestransformation/v2> would be better suited. What
we could do is also create a <https://api.transformation.nsgi.nl/v2> and have
that one forwarded to <https://api.nsgi.nl/coordinatestransformation/v2>

### old URL

<https://api.transformation.nsgi.nl/v1>

### new URL

<https://api.nsgi.nl/coordinatestransformation/v2>

## Docker

### Build container

```bash
docker build -t nsgi/coordinatestransformation-api .
```

### Run container

```bash
docker run --rm -d -p 8000:8000 --name ct-api nsgi/coordinatestransformation-api
```
