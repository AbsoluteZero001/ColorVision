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

from backend import __version__
from backend.main import APP_NAME, app
from backend.runtime import (
    request_shutdown,
    reset_shutdown,
    set_managed_runtime,
    wait_for_shutdown,
)
from backend.services.config_service import get_config_service
from backend.utils.logging_utils import setup_logging
from backend.utils.paths import (
    ensure_runtime_directories,
    get_app_root,
    get_cache_directory,
)

HOST = "127.0.0.1"
DEFAULT_PORT = 8000
STARTUP_TIMEOUT_SECONDS = 20.0
APP_MUTEX_NAME = "ColorVision_App_Running"

logger = logging.getLogger(__name__)


def _health_url(port: int) -> str:
    return f"http://{HOST}:{port}/api/health"


def _application_url(port: int) -> str:
    return f"http://{HOST}:{port}/"


def _probe_application(port: int) -> str | None:
    try:
        with urllib.request.urlopen(_health_url(port), timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None

    data = payload.get("data") if isinstance(payload, dict) else None
    if (
        response.status != 200
        or not isinstance(data, dict)
        or data.get("app") != APP_NAME
    ):
        return None

    running_version = data.get("version")
    return str(running_version) if running_version else "unknown"


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
        if server.started and _probe_application(port):
            return True
        if not server_thread.is_alive():
            return False
        time.sleep(0.1)
    return False


def _acquire_app_mutex() -> int | None:
    """Acquire a Windows named mutex so installers detect active instances."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        handle = ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
        return int(handle) if handle else None
    except Exception:
        logger.debug("Could not acquire Windows app mutex", exc_info=True)
        return None


def _release_app_mutex(handle: int | None) -> None:
    if handle is None or os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        logger.debug("Could not release Windows app mutex", exc_info=True)


def _write_runtime_cache(port: int) -> Path | None:
    """Persist lightweight session metadata under the unified cache directory."""
    cache_file = get_cache_directory() / "runtime-session.json"
    payload = {
        "app": APP_NAME,
        "version": __version__,
        "pid": os.getpid(),
        "port": port,
        "app_root": str(get_app_root()),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return cache_file
    except OSError:
        logger.warning("Could not write runtime session cache: %s", cache_file)
        return None


def _remove_runtime_cache(cache_file: Path | None) -> None:
    if cache_file is None:
        return
    try:
        cache_file.unlink(missing_ok=True)
    except OSError:
        logger.debug("Could not remove runtime session cache: %s", cache_file)


def main() -> int:
    """Start the application, open the browser, and wait for graceful shutdown."""
    setup_logging()
    ensure_runtime_directories()

    try:
        config_data = get_config_service().get_config()
    except Exception as exc:
        logger.exception("%s configuration initialization failed", APP_NAME)
        _show_message(
            f"{APP_NAME} 配置初始化失败：\n{exc}",
            f"{APP_NAME} 启动失败",
            error=True,
        )
        return 1

    port = config_data.port or DEFAULT_PORT
    application_url = _application_url(port)

    running_version = _probe_application(port)
    if running_version is not None:
        if running_version != __version__:
            message = (
                f"检测到 {APP_NAME} 旧版本正在运行。\n\n"
                f"当前运行版本：{running_version}\n"
                f"即将启动版本：{__version__}\n\n"
                "请先关闭旧版本后再启动当前版本。"
            )
            logger.error(
                "%s version mismatch on port %d: running=%s expected=%s",
                APP_NAME,
                port,
                running_version,
                __version__,
            )
            _show_message(message, f"{APP_NAME} 版本冲突", error=True)
            return 1

        logger.info("%s is already running on port %d", APP_NAME, port)
        _open_browser(application_url)
        _show_message(
            f"{APP_NAME} 已经运行，已打开现有页面：\n{application_url}",
            APP_NAME,
        )
        return 0

    if _port_is_in_use(port):
        message = (
            f"端口 {port} 已被其他程序占用。\n"
            "请关闭占用端口的程序，或修改 config/app.json 中的 port。"
        )
        logger.error(message.replace("\n", " "))
        _show_message(message, f"{APP_NAME} 启动失败", error=True)
        return 1

    mutex_handle = _acquire_app_mutex()
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
        _release_app_mutex(mutex_handle)
        message = (
            f"{APP_NAME} 本地服务未能在端口 {port} 正常启动。\n"
            "请查看 logs/colorvision.log。"
        )
        logger.error(message.replace("\n", " "))
        _show_message(message, f"{APP_NAME} 启动失败", error=True)
        return 1

    runtime_cache_file = _write_runtime_cache(port)
    logger.info("%s service ready: %s", APP_NAME, application_url)
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
        _remove_runtime_cache(runtime_cache_file)
        _release_app_mutex(mutex_handle)

    logger.info("%s process stopped", APP_NAME)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
