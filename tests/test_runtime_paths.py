"""Unified parent-directory and PyInstaller runtime path tests."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.utils.paths import (
    APP_ROOT_ENV,
    CONFIG_OVERRIDE_ENV,
    INSTALL_CONFIG_ENV,
    ensure_runtime_directories,
    get_api_config_path,
    get_app_config_path,
    get_app_root,
    get_bundled_config_path,
    get_cache_directory,
    get_camera_config_path,
    get_captures_directory,
    get_config_directory,
    get_data_directory,
    get_database_directory,
    get_database_path,
    get_frontend_dist_directory,
    get_history_directory,
    get_internal_directory,
    get_log_file_path,
    get_logs_directory,
    get_photos_directory,
    get_project_root,
    get_resource_root,
    get_runtime_config_path,
    get_uploaded_photos_directory,
)


class RuntimePathTests(unittest.TestCase):
    def test_frozen_layout_uses_unified_parent_directory(self) -> None:
        for custom_dir in ("ColorVision", "Software/ColorVision", "中文目录/ColorVision"):
            with self.subTest(install_dir=custom_dir):
                with TemporaryDirectory() as directory:
                    root = Path(directory) / custom_dir
                    internal = root / "_internal"
                    executable = root / "ColorVision.exe"
                    other_cwd = Path(directory) / "unrelated_cwd"
                    root.mkdir(parents=True, exist_ok=True)
                    internal.mkdir(parents=True, exist_ok=True)
                    other_cwd.mkdir(parents=True, exist_ok=True)

                    original_cwd = os.getcwd()
                    try:
                        os.chdir(other_cwd)
                        with (
                            patch.object(sys, "frozen", True, create=True),
                            patch.object(sys, "_MEIPASS", str(internal), create=True),
                            patch.object(sys, "executable", str(executable)),
                            patch.dict(
                                os.environ,
                                {
                                    APP_ROOT_ENV: "",
                                    INSTALL_CONFIG_ENV: "",
                                    CONFIG_OVERRIDE_ENV: "",
                                },
                            ),
                        ):
                            expected_root = root.resolve()
                            expected_internal = internal.resolve()

                            self.assertEqual(get_app_root(), expected_root)
                            self.assertEqual(get_project_root(), expected_root)
                            self.assertEqual(get_resource_root(), expected_internal)
                            self.assertEqual(get_internal_directory(), expected_internal)
                            self.assertEqual(get_config_directory(), expected_root / "config")
                            self.assertEqual(
                                get_app_config_path(),
                                expected_root / "config" / "app.json",
                            )
                            self.assertEqual(
                                get_api_config_path(),
                                expected_root / "config" / "api-config.json",
                            )
                            self.assertEqual(
                                get_camera_config_path(),
                                expected_root / "config" / "camera.json",
                            )
                            self.assertEqual(
                                get_runtime_config_path(),
                                expected_root / "config" / "app.json",
                            )
                            self.assertEqual(
                                get_bundled_config_path(),
                                expected_internal / "backend" / "config" / "config.json",
                            )
                            self.assertEqual(
                                get_frontend_dist_directory(),
                                expected_internal / "frontend" / "dist",
                            )
                            self.assertEqual(get_data_directory(), expected_root / "data")
                            self.assertEqual(
                                get_photos_directory(),
                                expected_root / "data" / "photos",
                            )
                            self.assertEqual(
                                get_captures_directory(),
                                expected_root / "data" / "photos" / "captures",
                            )
                            self.assertEqual(
                                get_uploaded_photos_directory(),
                                expected_root / "data" / "photos" / "uploads",
                            )
                            self.assertEqual(
                                get_history_directory(),
                                expected_root / "data" / "history",
                            )
                            self.assertEqual(
                                get_database_directory(),
                                expected_root / "data" / "database",
                            )
                            self.assertEqual(
                                get_database_path(),
                                expected_root / "data" / "database" / "colorvision.db",
                            )
                            self.assertEqual(get_cache_directory(), expected_root / "cache")
                            self.assertEqual(get_logs_directory(), expected_root / "logs")
                            self.assertEqual(
                                get_log_file_path(),
                                expected_root / "logs" / "colorvision.log",
                            )

                            dirs = ensure_runtime_directories()
                            for created in (
                                dirs.config,
                                dirs.photos,
                                dirs.captures,
                                dirs.uploads,
                                dirs.history,
                                dirs.database,
                                dirs.cache,
                                dirs.logs,
                            ):
                                self.assertTrue(created.is_dir())
                                rel = created.relative_to(expected_root)
                                self.assertNotIn("appdata", str(rel).lower())
                    finally:
                        os.chdir(original_cwd)

    def test_install_config_and_env_override_resolve_custom_root(self) -> None:
        with TemporaryDirectory() as directory:
            custom_root = (Path(directory) / "E_Drive" / "Software" / "ColorVision").resolve()
            config_dir = custom_root / "config"
            config_dir.mkdir(parents=True)
            app_json = config_dir / "app.json"
            app_json.write_text(
                json.dumps({"install_dir": str(custom_root)}),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    APP_ROOT_ENV: "",
                    INSTALL_CONFIG_ENV: str(app_json),
                },
            ):
                self.assertEqual(get_app_root(), custom_root)
                self.assertEqual(get_cache_directory(), custom_root / "cache")
                self.assertEqual(get_logs_directory(), custom_root / "logs")

            override_root = (Path(directory) / "OverrideRoot").resolve()
            with patch.dict(os.environ, {APP_ROOT_ENV: str(override_root)}):
                self.assertEqual(get_app_root(), override_root)
                self.assertEqual(
                    get_database_path(),
                    override_root / "data" / "database" / "colorvision.db",
                )

    def test_paths_never_resolve_into_appdata_env_roots(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "CustomInstall" / "ColorVision"
            forbidden_roaming = (Path(directory) / "FakeAppData" / "Roaming").resolve()
            forbidden_local = (Path(directory) / "FakeAppData" / "Local").resolve()
            root.mkdir(parents=True)

            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", str(root / "_internal"), create=True),
                patch.object(sys, "executable", str(root / "ColorVision.exe")),
                patch.dict(
                    os.environ,
                    {
                        APP_ROOT_ENV: "",
                        INSTALL_CONFIG_ENV: "",
                        CONFIG_OVERRIDE_ENV: "",
                        "APPDATA": str(forbidden_roaming),
                        "LOCALAPPDATA": str(forbidden_local),
                    },
                ),
            ):
                dirs = ensure_runtime_directories()
                for path in (
                    dirs.app_root,
                    dirs.config,
                    dirs.data,
                    dirs.photos,
                    dirs.history,
                    dirs.database,
                    dirs.cache,
                    dirs.logs,
                ):
                    self.assertFalse(path.is_relative_to(forbidden_roaming))
                    self.assertFalse(path.is_relative_to(forbidden_local))
                self.assertFalse(forbidden_roaming.exists())
                self.assertFalse(forbidden_local.exists())


if __name__ == "__main__":
    unittest.main()
