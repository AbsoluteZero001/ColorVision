"""Runtime-safe path resolution for source and PyInstaller execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return whether the process is running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_project_root() -> Path:
    """Resolve the writable application root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_resource_root() -> Path:
    """Resolve read-only resources embedded by PyInstaller."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return get_project_root()


def get_runtime_config_path() -> Path:
    """Return the external path used for user-editable configuration."""
    override = os.getenv("COLORVISION_CONFIG")
    if override:
        return Path(override).expanduser().resolve()

    if is_frozen():
        return get_project_root() / "config" / "config.json"
    return get_project_root() / "backend" / "config" / "config.json"


def get_bundled_config_path() -> Path:
    """Return the packaged default configuration path."""
    return get_resource_root() / "backend" / "config" / "config.json"


def get_frontend_dist_directory() -> Path:
    """Return the built Vue application directory."""
    return get_resource_root() / "frontend" / "dist"


def get_data_directory() -> Path:
    """Return the root for runtime-generated data."""
    return get_project_root() / "data"


def get_logs_directory() -> Path:
    """Return the log output directory."""
    return get_data_directory() / "logs"


def ensure_runtime_directories() -> tuple[Path, Path, Path]:
    """Create writable runtime directories and return captures/results/logs."""
    data_directory = get_data_directory()
    captures_directory = data_directory / "captures"
    results_directory = data_directory / "results"
    logs_directory = data_directory / "logs"
    log_images_directory = logs_directory / "images"
    for directory in (
        captures_directory,
        results_directory,
        logs_directory,
        log_images_directory,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return captures_directory, results_directory, logs_directory
