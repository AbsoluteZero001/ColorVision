"""Small image helpers shared by image and color services."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def build_capture_filename(extension: str = ".jpg") -> str:
    """Create a collision-resistant capture filename without hardcoded paths."""
    normalized = extension if extension.startswith(".") else f".{extension}"
    return f"capture_{uuid4().hex}{normalized.lower()}"


def ensure_parent_directory(path: Path) -> None:
    """Create a file's parent directory when it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
