"""Image persistence and retention policy tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from backend.models.config import AppConfig
from backend.services.image_service import ImageService


class ImageServiceRetentionTests(unittest.TestCase):
    def _create_service(
        self,
        directory: str,
        **config_values: int,
    ) -> ImageService:
        captures = Path(directory) / "captures"
        captures.mkdir()
        return ImageService(
            captures_directory=captures,
            results_directory=Path(directory) / "results",
            config_provider=lambda: AppConfig(**config_values),
        )

    def test_retention_is_disabled_by_default_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(directory)
            captures = service._captures_directory
            for index in range(3):
                (captures / f"capture-{index}.jpg").write_bytes(b"jpeg")

            deleted = service.enforce_retention()

            self.assertEqual(deleted, 0)
            self.assertEqual(len(list(captures.glob("*.jpg"))), 3)

    def test_max_image_count_removes_oldest_captures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(directory, max_image_count=2)
            captures = service._captures_directory
            for index in range(4):
                path = captures / f"capture-{index}.jpg"
                path.write_bytes(b"jpeg")
                os.utime(path, (100 + index, 100 + index))

            deleted = service.enforce_retention()

            self.assertEqual(deleted, 2)
            self.assertEqual(
                sorted(path.name for path in captures.glob("*.jpg")),
                ["capture-2.jpg", "capture-3.jpg"],
            )

    def test_retention_days_removes_expired_captures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(
                directory,
                image_retention_days=1,
            )
            captures = service._captures_directory
            old_file = captures / "old.jpg"
            recent_file = captures / "recent.jpg"
            old_file.write_bytes(b"old")
            recent_file.write_bytes(b"recent")
            os.utime(old_file, (1, 1))

            deleted = service.enforce_retention()

            self.assertEqual(deleted, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(recent_file.exists())


if __name__ == "__main__":
    unittest.main()
