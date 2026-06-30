from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


class ApiResponse(BaseModel, Generic[DataT]):
    data: DataT | None = None
    error: ErrorBody | None = None
    request_id: str | None = None
