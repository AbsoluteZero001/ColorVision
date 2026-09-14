"""Unified local launcher used by Python and PyInstaller execution."""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

# Allow ``python backend/launcher.py`` as well as module execution.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn

from backend.main import APP_NAME, app
from backend.runtime import (
    request_shutdown,
    reset_shutdown,
    set_managed_runtime,
    wait_for_shutdown,
)
from backend.services.config_service import get_config_service
from backend.utils.logging_utils import setup_logging
from backend.utils.paths import ensure_runtime_directories

HOST = "127.0.0.1"
DEFAULT_PORT = 8000
STARTUP_TIMEOUT_SECONDS = 20.0

logger = logging.getLogger(__name__)


def _health_url(port: int) -> str:
    return f"http://{HOST}:{port}/api/health"


def _application_url(port: int) -> str:
    return f"http://{HOST}:{port}/"


def _probe_colorvision(port: int) -> bool:
    try:
        with urllib.request.urlopen(_health_url(port), timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return False

    data = payload.get("data") if isinstance(payload, dict) else None
    return bool(
        response.status == 200
        and isinstance(data, dict)
        and data.get("app") == APP_NAME
    )


def _port_is_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((HOST, port)) == 0


def _show_message(message: str, title: str, error: bool = False) -> None:
    if os.getenv("COLORVISION_SUPPRESS_MESSAGES") == "1":
        logger.info("%s: %s", title, message.replace("\n", " "))
        return

    if getattr(sys, "frozen", False) and os.name == "nt":
        import ctypes

        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(None, message, title, flags)
        return

    output = sys.stderr if error else sys.stdout
    if output is not None:
        print(message, file=output)


def _open_browser(url: str) -> None:
    if os.getenv("COLORVISION_NO_BROWSER") == "1":
        logger.info("Browser auto-open disabled by environment")
        return
    try:
        opened = webbrowser.open(url, new=2, autoraise=True)
        if opened:
            logger.info("Browser opened: %s", url)
        else:
            logger.warning("Default browser did not accept the open request: %s", url)
    except Exception:
        logger.exception("Failed to open the default browser")


def _wait_for_server(
    server: uvicorn.Server,
    server_thread: threading.Thread,
    port: int,
) -> bool:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if server.started and _probe_colorvision(port):
            return True
        if not server_thread.is_alive():
            return False
        time.sleep(0.1)
    return False


def main() -> int:
    """Start ColorVision, open the browser, and wait for graceful shutdown."""
    setup_logging()
    ensure_runtime_directories()

    try:
        config_data = get_config_service().get_config()
    except Exception as exc:
        logger.exception("ColorVision configuration initialization failed")
        _show_message(
            f"ColorVision 配置初始化失败：\n{exc}",
            f"{APP_NAME} 启动失败",
            error=True,
        )
        return 1

    port = config_data.port or DEFAULT_PORT
    application_url = _application_url(port)

    if _probe_colorvision(port):
        logger.info("ColorVision is already running on port %d", port)
        _open_browser(application_url)
        _show_message(
            f"ColorVision 已经运行，已打开现有页面：\n{application_url}",
            APP_NAME,
        )
        return 0

    if _port_is_in_use(port):
        message = (
            f"端口 {port} 已被其他程序占用。\n"
            "请关闭占用端口的程序，或修改 config/config.json 中的 port。"
        )
        logger.error(message.replace("\n", " "))
        _show_message(message, f"{APP_NAME} 启动失败", error=True)
        return 1

    set_managed_runtime(True)
    reset_shutdown()
    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host=HOST,
            port=port,
            reload=False,
            access_log=False,
            log_level="warning",
            log_config=None,
        )
    )
    server.install_signal_handlers = lambda: None
    server_thread = threading.Thread(
        target=server.run,
        name="colorvision-uvicorn",
        daemon=False,
    )
    server_thread.start()

    if not _wait_for_server(server, server_thread, port):
        request_shutdown()
        server.should_exit = True
        server_thread.join(timeout=10)
        message = (
            f"ColorVision 本地服务未能在端口 {port} 正常启动。\n"
            "请查看 data/logs/colorvision.log。"
        )
        logger.error(message.replace("\n", " "))
        _show_message(message, f"{APP_NAME} 启动失败", error=True)
        return 1

    logger.info("ColorVision service ready: %s", application_url)
    _open_browser(application_url)

    try:
        while server_thread.is_alive():
            if wait_for_shutdown(0.5):
                logger.info("Graceful shutdown requested")
                break
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        server.should_exit = True
        server_thread.join(timeout=10)
        if server_thread.is_alive():
            logger.warning("Server thread did not stop within 10 seconds")

    logger.info("ColorVision process stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
