from typing import Any


class AppError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        detail: dict[str, Any] | None = None,
        recoverable: bool = False,
        suggested_action: str | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.recoverable = recoverable
        self.suggested_action = suggested_action
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(
        self,
        message: str,
        detail: dict[str, Any] | None = None,
        suggested_action: str | None = None,
    ) -> None:
        super().__init__(
            error_code="NOT_FOUND",
            message=message,
            detail=detail,
            recoverable=False,
            suggested_action=suggested_action,
            status_code=404,
        )


class ConflictError(AppError):
    def __init__(
        self,
        message: str,
        detail: dict[str, Any] | None = None,
        suggested_action: str | None = None,
    ) -> None:
        super().__init__(
            error_code="CONFLICT",
            message=message,
            detail=detail,
            recoverable=True,
            suggested_action=suggested_action,
            status_code=409,
        )


class ValidationAppError(AppError):
    def __init__(
        self,
        message: str,
        detail: dict[str, Any] | None = None,
        suggested_action: str | None = None,
    ) -> None:
        super().__init__(
            error_code="VALIDATION_ERROR",
            message=message,
            detail=detail,
            recoverable=True,
            suggested_action=suggested_action,
            status_code=422,
        )
