"""Unified parent-directory path resolution for source and packaged execution."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_ROOT_ENV = "COLORVISION_ROOT"
INSTALL_CONFIG_ENV = "COLORVISION_INSTALL_CONFIG"
CONFIG_OVERRIDE_ENV = "COLORVISION_CONFIG"


@dataclass(frozen=True, slots=True)
class RuntimeDirectories:
    """Resolved writable directories rooted under the unified app parent."""

    app_root: Path
    config: Path
    data: Path
    photos: Path
    captures: Path
    uploads: Path
    history: Path
    database: Path
    cache: Path
    logs: Path


def is_frozen() -> bool:
    """Return whether the process is running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def _read_install_dir_from_config(config_path: Path) -> Path | None:
    """Read an explicit install_dir from an install configuration JSON file."""
    if not config_path.is_file():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    raw_install_dir = payload.get("install_dir")
    if not isinstance(raw_install_dir, str) or not raw_install_dir.strip():
        return None
    candidate = Path(raw_install_dir.strip()).expanduser()
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def get_app_root() -> Path:
    """Resolve the unified installation/project root directory.

    Never hardcodes a drive letter and never falls back to AppData.
    """
    env_root = os.getenv(APP_ROOT_ENV)
    if env_root and env_root.strip():
        return Path(env_root.strip()).expanduser().resolve()

    install_config_override = os.getenv(INSTALL_CONFIG_ENV)
    if install_config_override and install_config_override.strip():
        configured_root = _read_install_dir_from_config(
            Path(install_config_override.strip()).expanduser().resolve()
        )
        if configured_root is not None:
            return configured_root

    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        # In packaged installs, ColorVision.exe sits directly inside the parent
        # install directory, regardless of process working directory.
        return exe_dir

    return Path(__file__).resolve().parents[2]


def get_project_root() -> Path:
    """Compatibility alias for get_app_root()."""
    return get_app_root()


def get_resource_root() -> Path:
    """Resolve read-only bundled resources (_internal in onedir PyInstaller)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def get_internal_directory() -> Path:
    """Return the runtime dependency directory (_internal in packaged builds)."""
    if is_frozen():
        return get_resource_root()
    return get_app_root()


def get_config_directory() -> Path:
    """Return the unified configuration directory (<root>/config)."""
    return get_app_root() / "config"


def get_app_config_path() -> Path:
    """Return the application & install configuration file (<root>/config/app.json)."""
    return get_config_directory() / "app.json"


def get_api_config_path() -> Path:
    """Return the upload API configuration file (<root>/config/api-config.json)."""
    return get_config_directory() / "api-config.json"


def get_camera_config_path() -> Path:
    """Return the camera configuration file (<root>/config/camera.json)."""
    return get_config_directory() / "camera.json"


def get_legacy_config_path() -> Path:
    """Return the legacy single-file config path (<root>/config/config.json)."""
    return get_config_directory() / "config.json"


def get_runtime_config_path() -> Path:
    """Return explicit COLORVISION_CONFIG override or the primary app config path."""
    override = os.getenv(CONFIG_OVERRIDE_ENV)
    if override and override.strip():
        return Path(override.strip()).expanduser().resolve()
    return get_app_config_path()


def get_bundled_config_path() -> Path:
    """Return the packaged default configuration template path."""
    return get_resource_root() / "backend" / "config" / "config.json"


def get_frontend_dist_directory() -> Path:
    """Return the built Vue application directory."""
    return get_resource_root() / "frontend" / "dist"


def get_data_directory() -> Path:
    """Return the root for runtime business data (<root>/data)."""
    return get_app_root() / "data"


def get_photos_directory() -> Path:
    """Return the unified photos root (<root>/data/photos)."""
    return get_data_directory() / "photos"


def get_captures_directory() -> Path:
    """Return the camera capture storage directory (<root>/data/photos/captures)."""
    return get_photos_directory() / "captures"


def get_uploaded_photos_directory() -> Path:
    """Return the uploaded photo storage directory (<root>/data/photos/uploads)."""
    return get_photos_directory() / "uploads"


def get_history_directory() -> Path:
    """Return the upload history directory (<root>/data/history)."""
    return get_data_directory() / "history"


def get_database_directory() -> Path:
    """Return the local SQLite database directory (<root>/data/database)."""
    return get_data_directory() / "database"


def get_database_path() -> Path:
    """Return the local SQLite database file (<root>/data/database/colorvision.db)."""
    return get_database_directory() / "colorvision.db"


def get_cache_directory() -> Path:
    """Return the unified cache directory (<root>/cache)."""
    return get_app_root() / "cache"


def get_logs_directory() -> Path:
    """Return the unified log output directory (<root>/logs)."""
    return get_app_root() / "logs"


def get_log_file_path() -> Path:
    """Return the main application log file (<root>/logs/colorvision.log)."""
    return get_logs_directory() / "colorvision.log"


def ensure_runtime_directories() -> RuntimeDirectories:
    """Create all writable runtime directories under the unified parent root."""
    dirs = RuntimeDirectories(
        app_root=get_app_root(),
        config=get_config_directory(),
        data=get_data_directory(),
        photos=get_photos_directory(),
        captures=get_captures_directory(),
        uploads=get_uploaded_photos_directory(),
        history=get_history_directory(),
        database=get_database_directory(),
        cache=get_cache_directory(),
        logs=get_logs_directory(),
    )
    for directory in (
        dirs.config,
        dirs.photos,
        dirs.captures,
        dirs.uploads,
        dirs.history,
        dirs.database,
        dirs.cache,
        dirs.logs,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return dirs
