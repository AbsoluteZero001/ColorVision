"""Camera API routes and MJPEG preview stream."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime

import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.models.camera import (
    CameraListData,
    CameraOpenRequest,
    CameraStatusData,
    CaptureData,
)
from backend.models.common import ApiResponse, ErrorCode
from backend.services.camera_service import get_camera_service
from backend.services.image_service import get_image_service
from backend.utils.errors import AppException

router = APIRouter(prefix="/camera", tags=["camera"])
logger = logging.getLogger(__name__)

STREAM_FPS = 15
STREAM_BOUNDARY = "frame"


@router.get("/list", response_model=ApiResponse[CameraListData])
async def list_cameras() -> ApiResponse[CameraListData]:
    """List available camera devices."""
    cameras = await asyncio.to_thread(get_camera_service().list_cameras)
    return ApiResponse(data=CameraListData(cameras=cameras))


@router.get("/status", response_model=ApiResponse[CameraStatusData])
async def camera_status() -> ApiResponse[CameraStatusData]:
    """Return the current camera state."""
    status = await asyncio.to_thread(get_camera_service().get_status)
    return ApiResponse(data=status)


@router.post("/open", response_model=ApiResponse[CameraStatusData])
async def open_camera(request: CameraOpenRequest) -> ApiResponse[CameraStatusData]:
    """Open a camera by index."""
    status = await asyncio.to_thread(
        get_camera_service().open_camera,
        request.index,
    )
    return ApiResponse(data=status)


@router.post("/close", response_model=ApiResponse[CameraStatusData])
async def close_camera() -> ApiResponse[CameraStatusData]:
    """Close the currently open camera."""
    status = await asyncio.to_thread(get_camera_service().close_camera)
    return ApiResponse(data=status)


@router.get("/stream")
async def stream_camera() -> StreamingResponse:
    """Stream live camera frames as multipart JPEG for an HTML image element."""
    service = get_camera_service()
    if not service.is_open:
        raise AppException(
            message="Camera is not open",
            code=ErrorCode.CAMERA_CLOSED,
            status_code=409,
        )

    return StreamingResponse(
        _mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={STREAM_BOUNDARY}",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _mjpeg_generator() -> AsyncIterator[bytes]:
    service = get_camera_service()
    frame_interval = 1 / STREAM_FPS
    while service.is_open:
        started_at = asyncio.get_running_loop().time()
        try:
            frame = await asyncio.to_thread(service.read_frame)
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 82],
            )
            if not ok:
                logger.warning("MJPEG frame encoding failed")
                continue

            jpeg = encoded.tobytes()
            yield (
                f"--{STREAM_BOUNDARY}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg)}\r\n\r\n"
            ).encode("ascii") + jpeg + b"\r\n"
        except AppException:
            logger.info("MJPEG stream stopped because the camera closed")
            break

        elapsed = asyncio.get_running_loop().time() - started_at
        await asyncio.sleep(max(0.0, frame_interval - elapsed))


@router.post("/capture", response_model=ApiResponse[CaptureData])
async def capture_frame() -> ApiResponse[CaptureData]:
    """Capture and persist one frame from the active camera."""
    camera_service = get_camera_service()
    frame = await asyncio.to_thread(camera_service.read_frame)
    image_service = get_image_service()
    image_path = await asyncio.to_thread(image_service.save_capture, frame)
    captured_at = datetime.now().astimezone().isoformat(timespec="milliseconds")
    logger.info("Capture API success: %s", image_path)
    return ApiResponse(
        data=CaptureData(
            image_path=image_service.build_project_path(image_path),
            image_url=image_service.build_media_url(image_path),
            captured_at=captured_at,
        )
    )
