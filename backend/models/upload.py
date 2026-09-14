"""Upload request result models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class UploadResultData(BaseModel):
    """Normalized result returned by mock or real external upload."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    request_id: str
    mode: Literal["mock", "api"]
    target_url: str | None = None
    upstream_status_code: int | None = None
    upstream_response: dict[str, Any] | None = None
