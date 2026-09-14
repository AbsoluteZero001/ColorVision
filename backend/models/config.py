"""Configuration models and validation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppConfig(BaseModel):
    """Persisted local application configuration."""

    model_config = ConfigDict(extra="forbid")

    api_url: str = "http://127.0.0.1:9000/api/color"
    token: str = ""
    camera_id: str = "CAM-001"
    auto_upload: bool = False
    mock_mode: bool = True
    request_timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("api_url must start with http:// or https://")
        return normalized

    @field_validator("camera_id")
    @classmethod
    def validate_camera_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("camera_id must not be empty")
        return normalized


class AppConfigUpdate(BaseModel):
    """Partial configuration update."""

    model_config = ConfigDict(extra="forbid")

    api_url: str | None = None
    token: str | None = None
    camera_id: str | None = None
    auto_upload: bool | None = None
    mock_mode: bool | None = None
    request_timeout_seconds: float | None = Field(default=None, gt=0, le=120)

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("api_url must start with http:// or https://")
        return normalized
