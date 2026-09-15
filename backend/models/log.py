"""Upload-log API models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.color import LABColor, RGBColor, RoiCoordinates


class UploadLogData(BaseModel):
    """One locally stored upload event."""

    model_config = ConfigDict(extra="forbid")

    id: int
    uploaded_at: str
    uploaded_at_beijing: str
    captured_at: str
    camera_id: str
    rgb: RGBColor
    lab: LABColor
    hex: str
    roi: RoiCoordinates
    upload_mode: Literal["mock", "api"]
    request_id: str
    message: str
    original_image_url: str | None = None
    roi_image_url: str | None = None


class UploadLogPage(BaseModel):
    """Paginated local upload-log response."""

    model_config = ConfigDict(extra="forbid")

    items: list[UploadLogData]
    total: int = Field(ge=0)
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)


class UploadLogDeleteData(BaseModel):
    """Deletion acknowledgement for one or more upload logs."""

    model_config = ConfigDict(extra="forbid")

    deleted: int = Field(ge=0)
