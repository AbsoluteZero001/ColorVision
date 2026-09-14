"""Camera API route definitions.

The endpoints are registered in Phase 1 so clients and OpenAPI are stable.
Hardware behavior is implemented by :mod:`backend.services.camera_service`
in a later phase.
"""

from fastapi import APIRouter

from backend.models.camera import (
    CameraListData,
    CameraOpenRequest,
    CameraStatusData,
    CaptureData,
)
from backend.models.common import ApiResponse, ErrorCode
from backend.utils.errors import AppException

router = APIRouter(prefix="/camera", tags=["camera"])


def _raise_not_implemented(operation: str) -> None:
    raise AppException(
        message=f"{operation} is not implemented yet",
        code=ErrorCode.FEATURE_NOT_IMPLEMENTED,
        status_code=501,
    )


@router.get("/list", response_model=ApiResponse[CameraListData])
async def list_cameras() -> ApiResponse[CameraListData]:
    """List available camera devices."""
    _raise_not_implemented("Camera listing")


@router.get("/status", response_model=ApiResponse[CameraStatusData])
async def camera_status() -> ApiResponse[CameraStatusData]:
    """Return the current camera state."""
    _raise_not_implemented("Camera status")


@router.post("/open", response_model=ApiResponse[CameraStatusData])
async def open_camera(request: CameraOpenRequest) -> ApiResponse[CameraStatusData]:
    """Open a camera by index."""
    _raise_not_implemented(f"Opening camera {request.index}")


@router.post("/close", response_model=ApiResponse[CameraStatusData])
async def close_camera() -> ApiResponse[CameraStatusData]:
    """Close the currently open camera."""
    _raise_not_implemented("Closing camera")


@router.post("/capture", response_model=ApiResponse[CaptureData])
async def capture_frame() -> ApiResponse[CaptureData]:
    """Capture and persist one frame from the active camera."""
    _raise_not_implemented("Frame capture")
