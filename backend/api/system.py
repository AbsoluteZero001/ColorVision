"""Managed-runtime system endpoints."""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from backend.models.common import ApiResponse, ErrorCode
from backend.runtime import is_managed_runtime, request_shutdown
from backend.utils.errors import AppException

router = APIRouter(prefix="/system", tags=["system"])


class ShutdownData(BaseModel):
    """Shutdown acknowledgement returned before the process exits."""

    model_config = ConfigDict(extra="forbid")

    shutting_down: bool


@router.post("/shutdown", response_model=ApiResponse[ShutdownData])
async def shutdown_application() -> ApiResponse[ShutdownData]:
    """Gracefully stop a launcher-managed application process."""
    if not is_managed_runtime():
        raise AppException(
            message="Shutdown is available only in the managed executable runtime",
            code=ErrorCode.INVALID_REQUEST,
            status_code=409,
        )

    asyncio.get_running_loop().call_later(0.2, request_shutdown)
    return ApiResponse(data=ShutdownData(shutting_down=True))
