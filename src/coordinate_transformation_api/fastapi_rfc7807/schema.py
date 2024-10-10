# copied from https://github.com/vapor-ware/fastapi-rfc7807
"""Pydantic model for the Problem response schema."""

from pydantic import BaseModel


class Problem(BaseModel):
    """Model of the RFC7807 Problem response schema."""

    type: str
    title: str
    status: int | None
    detail: str | None
    instance: str | None
