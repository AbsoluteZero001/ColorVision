"""JSON-backed configuration service using unified config/ files."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import ValidationError

from backend import __version__
from backend.models.common import ErrorCode
from backend.models.config import AppConfig, AppConfigUpdate
from backend.utils.errors import AppException
from backend.utils.paths import (
    CONFIG_OVERRIDE_ENV,
    get_app_root,
    get_bundled_config_path,
    get_config_directory,
)

logger = logging.getLogger(__name__)

APP_CONFIG_KEYS = (
    "port",
    "image_retention_days",
    "max_image_count",
    "log_enabled",
    "log_image_storage_enabled",
    "log_retention_days",
    "max_log_count",
)
API_CONFIG_KEYS = (
    "api_url",
    "token",
    "auto_upload",
    "mock_mode",
    "timeout",
)
CAMERA_CONFIG_KEYS = ("camera_id",)


class ConfigService:
    """Read and atomically persist validated application JSON configuration."""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        config_dir: Path | None = None,
    ) -> None:
        env_override = os.getenv(CONFIG_OVERRIDE_ENV)
        if config_path is not None:
            self._single_file_path: Path | None = config_path
            self._config_dir_override: Path | None = None
        elif config_dir is not None:
            self._single_file_path = None
            self._config_dir_override = config_dir
        elif env_override and env_override.strip():
            self._single_file_path = Path(env_override.strip()).expanduser().resolve()
            self._config_dir_override = None
        else:
            self._single_file_path = None
            self._config_dir_override = None
        self._lock = Lock()

    @property
    def config_directory(self) -> Path:
        if self._single_file_path is not None:
            return self._single_file_path.parent
        return self._config_dir_override or get_config_directory()

    @property
    def config_path(self) -> Path:
        if self._single_file_path is not None:
            return self._single_file_path
        return self.config_directory / "app.json"

    @property
    def app_config_path(self) -> Path:
        return self.config_directory / "app.json"

    @property
    def api_config_path(self) -> Path:
        return self.config_directory / "api-config.json"

    @property
    def camera_config_path(self) -> Path:
        return self.config_directory / "camera.json"

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
            try:
                updated = AppConfig.model_validate(merged)
            except ValidationError as exc:
                raise AppException(
                    message="Configuration update is invalid",
                    code=ErrorCode.INVALID_REQUEST,
                    status_code=422,
                ) from exc
            self._write_unlocked(updated)
            logger.info("Configuration updated at %s", self.config_path)
            return updated

    def _load_unlocked(self) -> AppConfig:
        if self._single_file_path is not None:
            return self._load_single_file_unlocked(self._single_file_path)
        return self._load_unified_unlocked()

    def _load_single_file_unlocked(self, source: Path) -> AppConfig:
        if not source.exists():
            config_data = self._default_config_from_bundle()
            self._write_single_file_unlocked(source, config_data)
            logger.info("Default configuration initialized at %s", source)
            return config_data

        try:
            raw = self._read_json(source)
            config_data = self._validate_and_migrate(raw)
            if set(raw) != set(config_data.model_dump()):
                self._write_single_file_unlocked(source, config_data)
                logger.info("Configuration migrated at %s", source)
            return config_data
        except (OSError, ValueError, ValidationError) as exc:
            logger.exception("Failed to read configuration from %s", source)
            raise AppException(
                message="Configuration could not be read",
                code=ErrorCode.CONFIG_READ_FAILED,
                status_code=500,
            ) from exc

    def _load_unified_unlocked(self) -> AppConfig:
        app_path = self.app_config_path
        api_path = self.api_config_path
        camera_path = self.camera_config_path
        legacy_path = self.config_directory / "config.json"

        existing_split = [
            path for path in (app_path, api_path, camera_path) if path.exists()
        ]
        if not existing_split:
            if legacy_path.exists():
                try:
                    legacy_raw = self._read_json(legacy_path)
                    config_data = self._validate_and_migrate(legacy_raw)
                except (OSError, ValueError, ValidationError) as exc:
                    logger.exception(
                        "Failed to migrate legacy configuration from %s",
                        legacy_path,
                    )
                    raise AppException(
                        message="Configuration could not be read",
                        code=ErrorCode.CONFIG_READ_FAILED,
                        status_code=500,
                    ) from exc
                self._write_unified_unlocked(config_data)
                logger.info(
                    "Migrated legacy config %s into %s",
                    legacy_path,
                    self.config_directory,
                )
                return config_data

            config_data = self._default_config_from_bundle()
            self._write_unified_unlocked(config_data)
            logger.info(
                "Default configuration initialized under %s",
                self.config_directory,
            )
            return config_data

        try:
            app_raw = self._read_json(app_path) if app_path.exists() else {}
            api_raw = self._read_json(api_path) if api_path.exists() else {}
            camera_raw = (
                self._read_json(camera_path) if camera_path.exists() else {}
            )

            app_settings = dict(app_raw)
            app_settings.pop("app_name", None)
            app_settings.pop("version", None)
            app_settings.pop("install_dir", None)

            merged: dict[str, Any] = {}
            if len(existing_split) < 3:
                merged.update(self._default_config_from_bundle().model_dump())
            merged.update(app_settings)
            merged.update(api_raw)
            merged.update(camera_raw)

            config_data = self._validate_and_migrate(merged)

            needs_write = len(existing_split) < 3
            if set(app_settings) != set(APP_CONFIG_KEYS):
                needs_write = True
            if set(api_raw) != set(API_CONFIG_KEYS):
                needs_write = True
            if set(camera_raw) != set(CAMERA_CONFIG_KEYS):
                needs_write = True
            if (
                app_raw.get("version") != __version__
                or app_raw.get("app_name") != "ColorVision"
                or not app_raw.get("install_dir")
            ):
                needs_write = True

            if needs_write:
                self._write_unified_unlocked(
                    config_data,
                    existing_app_meta=app_raw,
                )
                logger.info(
                    "Configuration synchronized under %s",
                    self.config_directory,
                )
            return config_data
        except (OSError, ValueError, ValidationError) as exc:
            logger.exception(
                "Failed to read unified configuration from %s",
                self.config_directory,
            )
            raise AppException(
                message="Configuration could not be read",
                code=ErrorCode.CONFIG_READ_FAILED,
                status_code=500,
            ) from exc

    def _default_config_from_bundle(self) -> AppConfig:
        bundled = get_bundled_config_path()
        if bundled.exists():
            try:
                raw = self._read_json(bundled)
                return self._validate_and_migrate(raw)
            except (OSError, ValueError, ValidationError):
                logger.warning(
                    "Bundled default configuration could not be parsed: %s",
                    bundled,
                )
        return AppConfig()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Configuration root must be a JSON object")
        return raw

    @staticmethod
    def _validate_and_migrate(raw: dict[str, Any]) -> AppConfig:
        normalized = dict(raw)
        legacy_timeout = normalized.pop("request_timeout_seconds", None)
        if legacy_timeout is not None and "timeout" not in normalized:
            normalized["timeout"] = legacy_timeout
        return AppConfig.model_validate(normalized)

    def _write_unlocked(self, config_data: AppConfig) -> None:
        if self._single_file_path is not None:
            self._write_single_file_unlocked(self._single_file_path, config_data)
        else:
            existing_meta: dict[str, Any] | None = None
            if self.app_config_path.exists():
                try:
                    existing_meta = self._read_json(self.app_config_path)
                except (OSError, ValueError):
                    existing_meta = None
            self._write_unified_unlocked(
                config_data,
                existing_app_meta=existing_meta,
            )

    def _write_single_file_unlocked(
        self,
        target_path: Path,
        config_data: AppConfig,
    ) -> None:
        self._write_json_atomic(target_path, config_data.model_dump())

    def _write_unified_unlocked(
        self,
        config_data: AppConfig,
        *,
        existing_app_meta: dict[str, Any] | None = None,
    ) -> None:
        dumped = config_data.model_dump()
        install_dir = str(
            (existing_app_meta or {}).get("install_dir") or get_app_root()
        )
        if self._config_dir_override is None:
            install_dir = str(get_app_root())

        app_payload: dict[str, Any] = {
            "app_name": "ColorVision",
            "version": __version__,
            "install_dir": install_dir,
        }
        for key in APP_CONFIG_KEYS:
            app_payload[key] = dumped[key]

        api_payload = {key: dumped[key] for key in API_CONFIG_KEYS}
        camera_payload = {key: dumped[key] for key in CAMERA_CONFIG_KEYS}

        self._write_json_atomic(self.app_config_path, app_payload)
        self._write_json_atomic(self.api_config_path, api_payload)
        self._write_json_atomic(self.camera_config_path, camera_payload)

    @staticmethod
    def _write_json_atomic(target_path: Path, payload: dict[str, Any]) -> None:
        temporary_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(target_path)
        except OSError as exc:
            logger.exception("Failed to write configuration to %s", target_path)
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
