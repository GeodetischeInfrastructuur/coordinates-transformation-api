import json
from typing import Annotated, Any, Literal, Union

from pydantic import (
    AfterValidator,
    Field,
    UrlConstraints,
)
from pydantic.fields import FieldInfo
from pydantic_core import Url
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)


class MyCustomSource(EnvSettingsSource):
    def prepare_field_value(
        self: Any,
        field_name: str,
        _: FieldInfo,
        value: Any,  # noqa: ANN401
        value_is_complex: bool,
    ) -> Any:  # noqa: ANN401
        if not value:
            return value
        if field_name == "cors_allow_origins":
            if value in ("null", "*"):
                return value
            return [str(x) for x in value.split(",")]
        if value_is_complex:
            return json.loads(value)
        else:
            return value


CorsAllOrNone = Literal["*"] | None


def check_path_empty(v: Url) -> Url:
    if v.path != "/":
        raise ValueError(
            f"path of setting cors_allow_origins url needs to be empty: {v}"
        )
    return v


AnyHttpUrl = Annotated[
    Url, UrlConstraints(allowed_schemes=["https"]), AfterValidator(check_path_empty)
]


class AppSettings(BaseSettings):
    request_timeout: int = Field(
        alias="REQUEST_TIMEOUT_SECONDS",
        default=10,
        description="request timeout in seconds",
    )
    max_size_request_body: int = Field(
        alias="MAX_SIZE_REQUEST_BODY",
        default=2000000,
        description="max size request body in bytes",
    )
    log_level: str = Field(alias="LOG_LEVEL", default="INFO")
    debug: bool = Field(
        alias="DEBUG",
        default=False,
        description="when debug=true, error message in http response are more verbose",
    )
    precision: int = Field(
        alias="PRECISION",
        default=4,
        description="number of decimals for output coordinates in GeoJSON format for CRS in meters, number of decimals for degrees-based CRS is PRECISION+5",
    )
    base_url: str = Field(
        alias="BASE_URL",
        default="http://localhost:8000/",
        description="base url on wich the API is served",
        pattern=r"^((https?:\/\/)?[\w-]+(\.[\w-]+)*\.?(:\d+)?(\/\S*)?)",  # adapted from https://codegolf.stackexchange.com/a/480
    )
    cors_allow_origins: Union[list[AnyHttpUrl], CorsAllOrNone] = Field(
        alias="CORS_ALLOW_ORIGINS",
        default=None,
        description="Cross-Origin Resource Sharing (CORS), either a comma separated list of HTTPS urls of the value `*` to allow CORS on all origins",
    )
    access_log: bool = Field(
        alias="ACCESS_LOG",
        default=False,
        description="enable access log, defaults to False",
    )
    api_key_in_oas: bool = Field(
        alias="API_KEY_IN_OAS",
        default=False,
        description="add required api key to oas document",
    )
    example_api_key: str | None = Field(
        alias="EXAMPLE_API_KEY",
        default=None,
        description="default api key to expose in oas document",
    )

    @classmethod
    def settings_customise_sources(  # type: ignore  # noqa: PLR0913
        cls: "AppSettings",
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:  # type: ignore
        return (MyCustomSource(settings_cls),)


app_settings = AppSettings()
