"""JSON-backed configuration service."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from threading import Lock

from pydantic import ValidationError

from backend.models.common import ErrorCode
from backend.models.config import AppConfig, AppConfigUpdate
from backend.utils.errors import AppException
from backend.utils.paths import (
    get_bundled_config_path,
    get_runtime_config_path,
)

logger = logging.getLogger(__name__)


class ConfigService:
    """Read and atomically persist validated application JSON configuration."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or get_runtime_config_path()
        self._lock = Lock()

    @property
    def config_path(self) -> Path:
        return self._config_path

    def get_config(self) -> AppConfig:
        """Load the current configuration from disk."""
        with self._lock:
            return self._load_unlocked()

    def update_config(self, update: AppConfigUpdate) -> AppConfig:
        """Merge a validated partial update and persist it."""
        with self._lock:
            current = self._load_unlocked()
            merged = current.model_dump()
            merged.update(update.model_dump(exclude_unset=True, exclude_none=True))
            updated = AppConfig.model_validate(merged)
            self._write_unlocked(updated)
            logger.info("Configuration updated at %s", self._config_path)
            return updated

    def _load_unlocked(self) -> AppConfig:
        source = self._config_path
        if not source.exists():
            bundled = get_bundled_config_path()
            if bundled.exists() and bundled != source:
                source = bundled
            else:
                default = AppConfig()
                self._write_unlocked(default)
                logger.info("Default configuration created at %s", self._config_path)
                return default

        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
            return AppConfig.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            logger.exception("Failed to read configuration from %s", source)
            raise AppException(
                message="Configuration could not be read",
                code=ErrorCode.CONFIG_READ_FAILED,
                status_code=500,
            ) from exc

    def _write_unlocked(self, config_data: AppConfig) -> None:
        temporary_path = self._config_path.with_suffix(
            f"{self._config_path.suffix}.tmp"
        )
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(config_data.model_dump(), ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self._config_path)
        except OSError as exc:
            logger.exception("Failed to write configuration to %s", self._config_path)
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Temporary configuration file could not be removed")
            raise AppException(
                message="Configuration could not be saved",
                code=ErrorCode.CONFIG_WRITE_FAILED,
                status_code=500,
            ) from exc


@lru_cache(maxsize=1)
def get_config_service() -> ConfigService:
    """Return the process-wide configuration service."""
    return ConfigService()
