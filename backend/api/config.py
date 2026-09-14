"""Local JSON configuration endpoints."""

from fastapi import APIRouter

from backend.models.common import ApiResponse
from backend.models.config import AppConfig, AppConfigUpdate
from backend.services.config_service import get_config_service

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ApiResponse[AppConfig])
async def get_config() -> ApiResponse[AppConfig]:
    """Read the current JSON configuration."""
    return ApiResponse(data=get_config_service().get_config())


@router.put("", response_model=ApiResponse[AppConfig])
async def update_config(payload: AppConfigUpdate) -> ApiResponse[AppConfig]:
    """Merge and persist supported configuration fields."""
    return ApiResponse(data=get_config_service().update_config(payload))
