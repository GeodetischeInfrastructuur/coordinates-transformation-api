# NL API

<https://gitdocumentatie.logius.nl/publicatie/api/adr/>

## Normative Design Rules

### functional rules

| rule | applicable | description |
| --- | --- | --- |
| /core/http-safety | :heavy_check_mark: | All operations are idempotent |
| /core/stateless | :heavy_check_mark: | No session state is maintained |
| /core/interface-language | :heavy_check_mark: | The API is in English, because the domain and terminology used is also in English. |
| /core/naming-resources | :heavy_check_mark: | `/transformation` and `/transform` |
| /core/nested-child | :grey_exclamation: | Non applicable |
| /core/resource-operations | :grey_exclamation: | Non applicable |
| /core/doc-language | :grey_exclamation: | Like mentioned regarding /core/interface-language, the domain and terminolgy used is English |
| /core/deprecation-schedule | :grey_exclamation: | Applicable, but implementation of the processes facilitating this will probably not be based primarily on email. Given the nature of the fact that this API will not be behind a registration. |
| /core/transition-period | :heavy_check_mark: | Applicable, we will move from `/v1` to a `/v2` |
| /core/hide-implementation | :heavy_check_mark: | Applicable |
| /core/naming-collections | :heavy_check_mark: | No collections available, singular resource like `/transformation` are standalone |
| /core/changelog | :heavy_check_mark: | Applicable, through open sourcing of the code on <https://github.com/GeodetischeInfrastructuur> |

### technical rules

| rule | applicable | description |
| --- | --- | --- |
| /core/http-methods | :heavy_check_mark: | Applicable, only `GET` and `POST` operations are supported |
| /core/doc-openapi | :heavy_check_mark: | The API has a OAS 3.0.3 document |
| /core/uri-version | :heavy_check_mark: | The API will have a `/v2` in the URI |
| /core/no-trailing-slash | :heavy_check_mark: | Applicable |
| /core/publish-openapi | :heavy_check_mark: | The OAS 3.0.3 document is available on `/openapi.json` endpoint |
| /core/semver | :heavy_check_mark: | Applicable |
| /core/version-header | :heavy_check_mark: | Applicable |
