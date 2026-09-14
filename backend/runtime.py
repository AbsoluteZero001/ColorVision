"""Process-local runtime state for managed launches and graceful shutdown."""

from __future__ import annotations

import os
import threading

MANAGED_RUNTIME_ENV = "COLORVISION_MANAGED_RUNTIME"

_shutdown_event = threading.Event()


def set_managed_runtime(enabled: bool = True) -> None:
    """Mark this process as running under the application launcher."""
    if enabled:
        os.environ[MANAGED_RUNTIME_ENV] = "1"
    else:
        os.environ.pop(MANAGED_RUNTIME_ENV, None)


def is_managed_runtime() -> bool:
    """Return whether the launcher controls this server process."""
    return os.getenv(MANAGED_RUNTIME_ENV) == "1"


def request_shutdown() -> None:
    """Request a graceful process shutdown."""
    _shutdown_event.set()


def reset_shutdown() -> None:
    """Clear a previous shutdown request."""
    _shutdown_event.clear()


def wait_for_shutdown(timeout: float | None = None) -> bool:
    """Wait for a graceful shutdown request."""
    return _shutdown_event.wait(timeout)
