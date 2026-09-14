"""Shared response and error models."""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ErrorCode(StrEnum):
    """Stable machine-readable error codes used by the frontend."""

    CAMERA_NOT_FOUND = "CAMERA_NOT_FOUND"
    CAMERA_NOT_AVAILABLE = "CAMERA_NOT_AVAILABLE"
    CAMERA_OPEN_FAILED = "CAMERA_OPEN_FAILED"
    CAMERA_CLOSED = "CAMERA_CLOSED"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    IMAGE_READ_FAILED = "IMAGE_READ_FAILED"
    INVALID_ROI = "INVALID_ROI"
    COLOR_ANALYSIS_FAILED = "COLOR_ANALYSIS_FAILED"
    API_REQUEST_FAILED = "API_REQUEST_FAILED"
    API_TIMEOUT = "API_TIMEOUT"
    CONFIG_READ_FAILED = "CONFIG_READ_FAILED"
    CONFIG_WRITE_FAILED = "CONFIG_WRITE_FAILED"
    INVALID_REQUEST = "INVALID_REQUEST"
    FEATURE_NOT_IMPLEMENTED = "FEATURE_NOT_IMPLEMENTED"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ApiResponse(BaseModel, Generic[T]):
    """Unified successful response envelope."""

    model_config = ConfigDict(extra="forbid")

    success: Literal[True] = True
    data: T
    message: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    """Unified failed response envelope."""

    model_config = ConfigDict(extra="forbid")

    success: Literal[False] = False
    message: str
    code: str
