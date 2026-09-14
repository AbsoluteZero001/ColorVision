"""Camera-related API models."""

from pydantic import BaseModel, ConfigDict, Field


class CameraInfo(BaseModel):
    """One camera device visible to the local machine."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    name: str
    available: bool


class CameraListData(BaseModel):
    """Response payload for camera enumeration."""

    model_config = ConfigDict(extra="forbid")

    cameras: list[CameraInfo]


class CameraStatusData(BaseModel):
    """Current state of the selected camera."""

    model_config = ConfigDict(extra="forbid")

    opened: bool
    index: int | None = None
    name: str | None = None
    available: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None


class CameraOpenRequest(BaseModel):
    """Camera selection request. The index is never assumed by API clients."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(default=0, ge=0)


class CaptureData(BaseModel):
    """Metadata returned after a frame is persisted."""

    model_config = ConfigDict(extra="forbid")

    image_path: str
    image_url: str
    captured_at: str
