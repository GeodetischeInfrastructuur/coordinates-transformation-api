from pydantic import Field
from pydantic_settings import BaseSettings


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
    log_level: str = Field(alias="LOG_LEVEL", default="ERROR")
    debug: bool = Field(
        alias="DEBUG",
        default=False,
        description="when debug=true, error message in http response are more verbose",
    )


app_settings = AppSettings()
