"""PyInstaller runtime path checks."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.utils.paths import (
    get_bundled_config_path,
    get_frontend_dist_directory,
    get_project_root,
    get_resource_root,
    get_runtime_config_path,
)


class RuntimePathTests(unittest.TestCase):
    def test_frozen_layout_uses_external_writable_and_bundled_readonly_roots(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "ColorVision" / "ColorVision.exe"
            resources = root / "_internal"

            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", str(resources), create=True),
                patch.object(sys, "executable", str(executable)),
                patch.dict(os.environ, {"COLORVISION_CONFIG": ""}),
            ):
                expected_root = executable.parent.resolve()
                expected_resources = resources.resolve()
                self.assertEqual(
                    get_project_root(),
                    expected_root,
                )
                self.assertEqual(get_resource_root(), expected_resources)
                self.assertEqual(
                    get_runtime_config_path(),
                    expected_root / "config" / "config.json",
                )
                self.assertEqual(
                    get_bundled_config_path(),
                    expected_resources / "backend" / "config" / "config.json",
                )
                self.assertEqual(
                    get_frontend_dist_directory(),
                    expected_resources / "frontend" / "dist",
                )


if __name__ == "__main__":
    unittest.main()
