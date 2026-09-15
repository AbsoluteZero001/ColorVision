"""Launcher startup behavior tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from backend import __version__
from backend.launcher import main
from backend.models.config import AppConfig


class LauncherTests(unittest.TestCase):
    def _run_main(
        self,
        running_version: str,
        *,
        show_message,
        open_browser,
    ) -> int:
        config_service = unittest.mock.Mock()
        config_service.get_config.return_value = AppConfig(port=8123)
        with (
            patch("backend.launcher.setup_logging"),
            patch("backend.launcher.ensure_runtime_directories"),
            patch(
                "backend.launcher.get_config_service",
                return_value=config_service,
            ),
            patch(
                "backend.launcher._probe_application",
                return_value=running_version,
            ),
            patch("backend.launcher._show_message", show_message),
            patch("backend.launcher._open_browser", open_browser),
        ):
            return main()

    def test_same_version_keeps_existing_launch_behavior(self) -> None:
        show_message = unittest.mock.Mock()
        open_browser = unittest.mock.Mock()

        exit_code = self._run_main(
            __version__,
            show_message=show_message,
            open_browser=open_browser,
        )

        self.assertEqual(exit_code, 0)
        open_browser.assert_called_once_with("http://127.0.0.1:8123/")
        self.assertIn("已经运行", show_message.call_args.args[0])

    def test_different_version_reports_conflict_without_opening_old_page(
        self,
    ) -> None:
        show_message = unittest.mock.Mock()
        open_browser = unittest.mock.Mock()

        exit_code = self._run_main(
            "1.2.0",
            show_message=show_message,
            open_browser=open_browser,
        )

        self.assertEqual(exit_code, 1)
        open_browser.assert_not_called()
        message = show_message.call_args.args[0]
        self.assertIn("旧版本正在运行", message)
        self.assertIn("当前运行版本：1.2.0", message)
        self.assertIn(f"即将启动版本：{__version__}", message)


if __name__ == "__main__":
    unittest.main()
