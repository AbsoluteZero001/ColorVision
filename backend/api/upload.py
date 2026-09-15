"""Upload API route and multipart validation."""

import asyncio
import logging
import re

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import ValidationError

from backend.models.color import LABColor, RGBColor, RoiCoordinates
from backend.models.common import ApiResponse, ErrorCode
from backend.models.upload import UploadResultData
from backend.services.color_service import get_color_service
from backend.services.image_service import get_image_service
from backend.services.log_service import get_log_service
from backend.services.upload_service import UploadPayload, get_upload_service
from backend.utils.errors import AppException

router = APIRouter(tags=["upload"])
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


async def _read_upload(
    upload: UploadFile,
    field_name: str,
) -> bytes:
    try:
        content = await upload.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await upload.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppException(
            message=f"{field_name} exceeds the 25 MB limit",
            code=ErrorCode.API_REQUEST_FAILED,
            status_code=413,
        )
    if not content:
        raise AppException(
            message=f"{field_name} is empty",
            code=ErrorCode.INVALID_REQUEST,
            status_code=422,
        )
    return content


def _parse_model(raw_value: str, model_type: type, field_name: str):
    try:
        return model_type.model_validate_json(raw_value)
    except ValidationError as exc:
        raise AppException(
            message=f"{field_name} contains invalid JSON values",
            code=ErrorCode.INVALID_REQUEST,
            status_code=422,
        ) from exc


@router.post("/upload", response_model=ApiResponse[UploadResultData])
async def upload_result(
    original_image: UploadFile = File(...),
    roi_image: UploadFile = File(...),
    rgb: str = Form(...),
    lab: str = Form(...),
    hex_value: str = Form(..., alias="hex"),
    roi: str = Form(...),
    camera_id: str = Form(...),
    timestamp: str = Form(...),
) -> ApiResponse[UploadResultData]:
    """Send capture metadata and images to the configured external API."""
    parsed_rgb = _parse_model(rgb, RGBColor, "rgb")
    parsed_lab = _parse_model(lab, LABColor, "lab")
    parsed_roi = _parse_model(roi, RoiCoordinates, "roi")

    if not HEX_PATTERN.fullmatch(hex_value):
        raise AppException(
            message="hex must use the #RRGGBB format",
            code=ErrorCode.INVALID_REQUEST,
            status_code=422,
        )
    expected_hex = get_color_service().rgb_to_hex(
        (parsed_rgb.r, parsed_rgb.g, parsed_rgb.b)
    )
    if hex_value.upper() != expected_hex:
        raise AppException(
            message="hex does not match the RGB values",
            code=ErrorCode.INVALID_REQUEST,
            status_code=422,
        )
    if not camera_id.strip() or not timestamp.strip():
        raise AppException(
            message="camera_id and timestamp must not be empty",
            code=ErrorCode.INVALID_REQUEST,
            status_code=422,
        )

    original_content = await _read_upload(original_image, "original_image")
    roi_content = await _read_upload(roi_image, "roi_image")
    image_service = get_image_service()
    original_decoded = await asyncio.to_thread(
        image_service.decode_image,
        original_content,
    )
    roi_decoded = await asyncio.to_thread(
        image_service.decode_image,
        roi_content,
    )
    await asyncio.to_thread(
        image_service.crop_roi,
        original_decoded,
        parsed_roi.x,
        parsed_roi.y,
        parsed_roi.width,
        parsed_roi.height,
    )
    if roi_decoded.shape[:2] != (parsed_roi.height, parsed_roi.width):
        raise AppException(
            message="roi_image dimensions do not match the ROI coordinates",
            code=ErrorCode.INVALID_REQUEST,
            status_code=422,
        )

    payload = UploadPayload(
        original_image=original_content,
        original_filename=original_image.filename or "original.jpg",
        original_content_type=original_image.content_type or "image/jpeg",
        roi_image=roi_content,
        roi_filename=roi_image.filename or "roi.jpg",
        roi_content_type=roi_image.content_type or "image/jpeg",
        rgb=parsed_rgb.model_dump(),
        lab=parsed_lab.model_dump(),
        hex=expected_hex,
        roi=parsed_roi.model_dump(),
        camera_id=camera_id.strip(),
        timestamp=timestamp.strip(),
    )
    result = await get_upload_service().upload(payload)
    try:
        await asyncio.to_thread(
            get_log_service().record_upload,
            payload,
            result,
        )
    except Exception:
        logger.exception("Successful upload could not be written to the local log")
    return ApiResponse(data=result)
