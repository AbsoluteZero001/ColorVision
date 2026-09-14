"""Color-analysis API route definition."""

from fastapi import APIRouter, File, Form, UploadFile

from backend.models.color import ColorAnalysisData
from backend.models.common import ApiResponse, ErrorCode
from backend.utils.errors import AppException

router = APIRouter(prefix="/color", tags=["color"])


@router.post("/analyze", response_model=ApiResponse[ColorAnalysisData])
async def analyze_color(
    image: UploadFile = File(...),
    x: int = Form(..., ge=0),
    y: int = Form(..., ge=0),
    width: int = Form(..., gt=0),
    height: int = Form(..., gt=0),
) -> ApiResponse[ColorAnalysisData]:
    """Analyze the average color inside an image ROI."""
    del image, x, y, width, height
    raise AppException(
        message="Color analysis is not implemented yet",
        code=ErrorCode.FEATURE_NOT_IMPLEMENTED,
        status_code=501,
    )
