# OGC API Common

<https://docs.ogc.org/is/19-072/19-072.html>

## Requirements

| requirement | applicable | description |
| --- | --- | --- |
| /req/core/http | :heavy_check_mark: | All operations are over HTTP(S)|
| /req/core/query-param-name-unknown | :x: | **Needs to be implemented**, correct implementation in the handling of query params |
| /req/core/query-param-value-invalid | :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-capitalization| :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-list-delimiter| :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-list-escape | :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-list-empty | :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-value-boolean | :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-value-integer | :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-value-decimal | :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/core/query-param-value-double| :x: | **Needs to be implemented**, see `/req/core/query-param-name-unknown` |
| /req/landing-page/root-op | :heavy_check_mark: | Returns the landing page |
| /req/landing-page/root-success | :x: | **Needs to be implemented** |
| /req/landing-page/api-definition-op | :x: | **Needs to be implemented** |
| /req/landing-page/api-definition-success | :x: | **Needs to be implemented** |
| /req/landing-page/conformance-op | :x: | **Needs to be implemented** |
| /req/landing-page/conformance-success | :x: | **Needs to be implemented** |
| /req/html/definition | :x: | **Needs to be implemented**, `text/html` response for LandingPage and Conformance documents |
| /req/html/content | :x: | **Needs to be implemented**, returns HTML5 document |
| /req/json/definition | :x: | **Needs to be implemented**, `application/json` response for LandingPage and Conformance documents |
| /req/json/content | :x: | **Needs to be implemented**, LandingPage and Conformance documents need to conform to the correct json schem |
| /req/oas30/oas-definition-1 | :grey_exclamation: | both JSON and HTML version of the API definition need to be available. The response header `application/vnd.oai.openapi+json;version=3.0` needs to be implemented for the OAS doc |
| /req/oas30/oas-definition-2 | :heavy_check_mark: | document conform OAS 3.0 |
| /req/oas30/oas-impl | :heavy_check_mark: | no missing or incomplete api operations |
| /req/oas30/completeness | :grey_exclamation: | response objects need to be defined |
| /req/oas30/exceptions-codes | :heavy_check_mark: | yes |
| /req/oas30/security | :heavy_check_mark: | nonapplicable |

## Recommendations

| recommendation | applicable | description |
| --- | --- | --- |
| /rec/core/link-header | :grey_exclamation: | Needs to be decided and if so what to link |
| /per/core/additional-status-codes | :grey_exclamation: | Needs to be decided and if so what what kind of additional status codes |
| /rec/core/problem-details | :x: | **Needs to be implemented** |
| /per/core/query-param-name-specified | :grey_exclamation: | nonapplicable |
| /per/core/query-param-name-tolerance | :grey_exclamation: | won't do |
| /per/core/query-param-value-specified | :x: | **Needs to be implemented** |
| /per/core/query-param-value-tolerance | :grey_exclamation: | won't do |
| /rec/core/etag | :x: | **Needs to be implemented** |
| /rec/core/cross-origin | :x: | **Needs to be implemented** |
| /rec/core/string-i18n | :x: | **Needs to be implemented** |
| /rec/core/html | :x: | **Needs to be implemented**, need to think about how to visualise the original input vs the transformed output |
| /rec/core/json | :heavy_check_mark: | yes |
| /rec/core/query-param-capitalization | :heavy_check_mark: | yes |
| /rec/core/query-param-value-special | :heavy_check_mark: | oke |
| /rec/landing-page/api-definition-op | :x: | **Needs to be implemented**, `/api` SHOULD be implementend. MAY use -f parameter to satisfy this requiremen |
| /rec/landing-page/api-definition-oas | :heavy_check_mark: | yes |
| /rec/html/schema-org | :x: | **Needs to be implemented**, `text/html` responses SHOULD include schema.org annotations |
| /rec/json/problem-details | :x: | **Needs to be implemented**, error respones need to set `content-type: application/problem+json` and structured following this [JSON schema](https://github.com/opengeospatial/ogcapi-common/blob/master/collections/openapi/schemas/exception.json) |
