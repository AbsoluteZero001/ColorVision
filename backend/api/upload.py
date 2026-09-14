"""External upload API route definition."""

from fastapi import APIRouter, File, Form, UploadFile

from backend.models.common import ApiResponse, ErrorCode
from backend.utils.errors import AppException

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=ApiResponse[dict[str, str]])
async def upload_result(
    original_image: UploadFile = File(...),
    roi_image: UploadFile = File(...),
    rgb: str = Form(...),
    lab: str = Form(...),
    hex_value: str = Form(..., alias="hex"),
    camera_id: str = Form(...),
    timestamp: str = Form(...),
) -> ApiResponse[dict[str, str]]:
    """Send capture metadata and images to the configured external API."""
    del original_image, roi_image, rgb, lab, hex_value, camera_id, timestamp
    raise AppException(
        message="Upload is not implemented yet",
        code=ErrorCode.FEATURE_NOT_IMPLEMENTED,
        status_code=501,
    )
