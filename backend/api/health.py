"""System health endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from backend import APP_NAME, __version__
from backend.models.common import ApiResponse
from backend.runtime import is_managed_runtime
from backend.services.config_service import get_config_service

router = APIRouter(prefix="/health", tags=["system"])


class HealthData(BaseModel):
    """Health payload returned to the local frontend."""

    model_config = ConfigDict(extra="forbid")

    status: str
    app: str
    version: str
    mock_mode: bool
    managed_runtime: bool


@router.get("", response_model=ApiResponse[HealthData])
async def get_health() -> ApiResponse[HealthData]:
    """Return local service health and the active mock-upload setting."""
    config_data = get_config_service().get_config()
    return ApiResponse(
        data=HealthData(
            status="ok",
            app=APP_NAME,
            version=__version__,
            mock_mode=config_data.mock_mode,
            managed_runtime=is_managed_runtime(),
        )
    )
