"""Color-analysis API route."""

import asyncio

from fastapi import APIRouter, File, Form, UploadFile

from backend.models.color import ColorAnalysisData
from backend.models.common import ApiResponse, ErrorCode
from backend.services.color_service import get_color_service
from backend.services.image_service import get_image_service
from backend.utils.errors import AppException

router = APIRouter(prefix="/color", tags=["color"])
MAX_IMAGE_BYTES = 25 * 1024 * 1024


@router.post("/analyze", response_model=ApiResponse[ColorAnalysisData])
async def analyze_color(
    image: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...),
) -> ApiResponse[ColorAnalysisData]:
    """Analyze the average color inside an image ROI."""
    try:
        content = await image.read(MAX_IMAGE_BYTES + 1)
    finally:
        await image.close()

    if len(content) > MAX_IMAGE_BYTES:
        raise AppException(
            message="Uploaded image exceeds the 25 MB limit",
            code=ErrorCode.IMAGE_READ_FAILED,
            status_code=413,
        )

    decoded = await asyncio.to_thread(get_image_service().decode_image, content)
    result = await asyncio.to_thread(
        get_color_service().analyze_roi,
        decoded,
        x,
        y,
        width,
        height,
    )
    return ApiResponse(data=result)
