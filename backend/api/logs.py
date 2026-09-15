"""Local upload-log endpoints."""

import asyncio

from fastapi import APIRouter, Query

from backend.models.common import ApiResponse
from backend.models.log import UploadLogDeleteData, UploadLogPage
from backend.services.log_service import get_log_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=ApiResponse[UploadLogPage])
async def list_upload_logs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ApiResponse[UploadLogPage]:
    """Return newest local upload logs first."""
    page = await asyncio.to_thread(
        get_log_service().list_entries,
        limit,
        offset,
    )
    return ApiResponse(data=page)


@router.delete("/{log_id}", response_model=ApiResponse[UploadLogDeleteData])
async def delete_upload_log(log_id: int) -> ApiResponse[UploadLogDeleteData]:
    """Delete one local upload log and its images."""
    deleted = await asyncio.to_thread(
        get_log_service().delete_entry,
        log_id,
    )
    return ApiResponse(data=UploadLogDeleteData(deleted=deleted))


@router.delete("", response_model=ApiResponse[UploadLogDeleteData])
async def clear_upload_logs() -> ApiResponse[UploadLogDeleteData]:
    """Delete all local upload logs and their images."""
    deleted = await asyncio.to_thread(get_log_service().clear_entries)
    return ApiResponse(data=UploadLogDeleteData(deleted=deleted))
