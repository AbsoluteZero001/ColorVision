"""Application-level exceptions."""

from __future__ import annotations

from backend.models.common import ErrorCode


class AppException(Exception):
    """An expected error that maps to the unified API error response."""

    def __init__(
        self,
        message: str,
        code: ErrorCode | str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = str(code)
        self.status_code = status_code
