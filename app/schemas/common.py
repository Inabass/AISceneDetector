from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ErrorBody(BaseModel):
    error_code: str
    message: str
    detail: dict[str, object] | None = None
    recoverable: bool
    suggested_action: str | None = None
    request_id: str | None = None


class ApiResponse(BaseModel, Generic[DataT]):
    data: DataT | None = None
    error: ErrorBody | None = None
    request_id: str | None = None
