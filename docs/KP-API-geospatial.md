# API Design rules Module: Geospatial

<https://docs.geostandaarden.nl/api/API-Strategie-mod-geo/>

## Recommendation

| recommendation | applicable | description |
| --- | --- | --- |
| JSON-based encoding | :heavy_check_mark: | |
| consider text/html | :heavy_check_mark: | |
| GeoJSON | :heavy_check_mark: | Limitations regarding GeoJSON are described in this document, but these are not applicable to our API. Because we do not generate new objects or features, we only transform the geometry of a given feature. |

## Rules

| rule | applicable | description |
| --- | --- | --- |
| /geo/bbox-query-parameter | :grey_exclamation: | nonapplicable |
| /geo/geometric-context | :grey_exclamation: | nonapplicable |
| /geo/geojson-request | :grey_exclamation: | GeoJSON response have the header `application/json` instead of `application/geo+json` because GeoJSON is only WGS84 and we transform our GeoJSON to other CRS | |
| /geo/embed-geojson-geometry-request | :grey_exclamation: | nonapplicable |
| /geo/geojson-response | :grey_exclamation: | nonapplicable |
| /geo/embed-geojson-geometry-response | :grey_exclamation: | nonapplicable |
| /geo/crs-list | :x: | **Needs to be implemented** |
| /geo/storage-crs | :grey_exclamation: | nonapplicable, we don't store data |
| /geo/default-crs | :grey_exclamation: | nonapplicable, the service is build around RDNAPTRANS(r), so the default is EPSG:7415 not CRS84 |
| /geo/preferred-crs | :heavy_check_mark: | We return data in RD and ETRS89 |
| /geo/ensemble-member-crs | :grey_exclamation: | nonapplicable |
| /geo/bbox-crs-query-parameter | :grey_exclamation: | nonapplicable |
| /geo/filter-crs-query-parameter | :grey_exclamation: | nonapplicable |
| /geo/content-crs-request-header | :x: | Content CRS is now negotiated through query parameters and the feature it self. Adding a third option would bloat the API. |
| /geo/crs-query-paramete | :x: | We don't use the CRS query parameter because we need 2 CRS for our API. Using a named one like source-crs and target-crs makes it clear what the purpose is |
| /geo/content-crs-response-header | :grey_exclamation: | nonapplicable, response crs is know through the requested target-crs |
