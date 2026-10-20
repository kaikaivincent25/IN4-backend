from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class RequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel, Generic[T]):
    count: int = Field(ge=0)
    next: str | None
    previous: str | None
    results: list[T]


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str | None = None
    errors: dict[str, list[str]]
