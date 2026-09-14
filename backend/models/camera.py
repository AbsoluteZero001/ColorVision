"""Camera-related API models."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CameraState(StrEnum):
    """Unified lifecycle state exposed by the camera service."""

    INITIALIZING = "initializing"
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    OPEN_FAILED = "open_failed"
    BUSY = "busy"
    DISCONNECTED = "disconnected"
    READ_FAILED = "read_failed"
    MOCK = "mock"
    CLOSED = "closed"


class CameraSourceType(StrEnum):
    """Frame source selected by the camera service."""

    REAL = "real"
    MOCK = "mock"


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
    state: CameraState = CameraState.INITIALIZING
    message: str | None = None
    code: str | None = None


class CameraStatusData(BaseModel):
    """Current state of the selected camera."""

    model_config = ConfigDict(extra="forbid")

    state: CameraState = CameraState.INITIALIZING
    source: CameraSourceType | None = None
    camera_id: str | None = None
    opened: bool = False
    index: int | None = None
    name: str | None = None
    available: bool = False
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    message: str | None = None
    code: str | None = None


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
