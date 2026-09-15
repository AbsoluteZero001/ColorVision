"""SQLite upload-log persistence and retention tests."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from backend.models.config import AppConfig
from backend.models.upload import UploadResultData
from backend.services.log_service import LogService
from backend.services.upload_service import UploadPayload


def make_payload() -> UploadPayload:
    return UploadPayload(
        original_image=b"original-jpeg",
        original_filename="original.jpg",
        original_content_type="image/jpeg",
        roi_image=b"roi-jpeg",
        roi_filename="roi.jpg",
        roi_content_type="image/jpeg",
        rgb={"r": 120, "g": 35, "b": 40},
        lab={"l": 27.84, "a": 37.0, "b": 18.0},
        hex="#782328",
        roi={"x": 10, "y": 20, "width": 60, "height": 40},
        camera_id="CAM-TEST",
        timestamp="2026-09-15T20:00:00+08:00",
    )


def make_result(request_id: str = "MOCK-20260915-0001") -> UploadResultData:
    return UploadResultData(
        success=True,
        message="Mock upload success",
        request_id=request_id,
        mode="mock",
    )


class LogServiceTests(unittest.TestCase):
    def _create_service(
        self,
        directory: str,
        **config_values: object,
    ) -> LogService:
        return LogService(
            logs_directory=Path(directory) / "data" / "logs",
            config_provider=lambda: AppConfig(**config_values),
            now_provider=lambda: datetime(
                2026,
                9,
                15,
                12,
                34,
                56,
                tzinfo=timezone.utc,
            ),
        )

    def test_initialize_creates_empty_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(directory)

            service.initialize()

            self.assertTrue(service.database_path.is_file())
            with closing(sqlite3.connect(service.database_path)) as connection:
                row_count = connection.execute(
                    "SELECT COUNT(*) FROM upload_logs"
                ).fetchone()[0]
            self.assertEqual(row_count, 0)
            self.assertEqual(service.list_entries().total, 0)

    def test_record_lists_beijing_time_and_local_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(
                directory,
                log_enabled=True,
                log_image_storage_enabled=True,
            )

            entry = service.record_upload(make_payload(), make_result())
            page = service.list_entries()

            self.assertIsNotNone(entry)
            self.assertEqual(entry.uploaded_at_beijing, "2026-09-15 20:34:56")
            self.assertEqual(entry.uploaded_at, "2026-09-15T20:34:56+08:00")
            self.assertEqual(entry.rgb.r, 120)
            self.assertEqual(entry.lab.l, 27.84)
            self.assertEqual(entry.roi.width, 60)
            self.assertEqual(page.total, 1)
            self.assertEqual(page.items[0].request_id, "MOCK-20260915-0001")
            self.assertIsNotNone(page.items[0].original_image_url)
            self.assertIsNotNone(page.items[0].roi_image_url)
            self.assertTrue(
                page.items[0].original_image_url.startswith(
                    "/media/logs/images/"
                )
            )
            self.assertTrue(
                page.items[0].roi_image_url.startswith(
                    "/media/logs/images/"
                )
            )
            self.assertEqual(
                len(list(service.images_directory.glob("*.jpg"))),
                2,
            )

    def test_image_storage_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(
                directory,
                log_enabled=True,
                log_image_storage_enabled=False,
            )

            entry = service.record_upload(make_payload(), make_result())

            self.assertIsNotNone(entry)
            self.assertIsNone(entry.original_image_url)
            self.assertIsNone(entry.roi_image_url)
            self.assertEqual(list(service.images_directory.iterdir()), [])

    def test_delete_and_clear_remove_associated_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(
                directory,
                log_enabled=True,
                log_image_storage_enabled=True,
            )
            first = service.record_upload(make_payload(), make_result("MOCK-1"))
            second = service.record_upload(make_payload(), make_result("MOCK-2"))
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)

            deleted = service.delete_entry(first.id)

            self.assertEqual(deleted, 1)
            self.assertEqual(
                len(list(service.images_directory.glob("*.jpg"))),
                2,
            )
            remaining = service.list_entries()
            self.assertEqual(remaining.total, 1)
            self.assertEqual(remaining.items[0].id, second.id)

            cleared = service.clear_entries()

            self.assertEqual(cleared, 1)
            self.assertEqual(service.list_entries().total, 0)
            self.assertEqual(list(service.images_directory.iterdir()), [])

    def test_max_log_count_removes_oldest_entries_and_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self._create_service(
                directory,
                log_enabled=True,
                log_image_storage_enabled=True,
                max_log_count=2,
            )

            for index in range(3):
                service.record_upload(
                    make_payload(),
                    make_result(f"MOCK-{index}"),
                )

            page = service.list_entries()

            self.assertEqual(page.total, 2)
            self.assertEqual(
                [entry.request_id for entry in page.items],
                ["MOCK-2", "MOCK-1"],
            )
            self.assertEqual(
                len(list(service.images_directory.glob("*.jpg"))),
                4,
            )

    def test_retention_days_removes_expired_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current_time = [
                datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc)
            ]
            service = LogService(
                logs_directory=Path(directory) / "logs",
                config_provider=lambda: AppConfig(
                    log_enabled=True,
                    log_image_storage_enabled=True,
                    log_retention_days=1,
                ),
                now_provider=lambda: current_time[0],
            )
            service.record_upload(make_payload(), make_result("OLD"))

            current_time[0] = datetime(
                2026,
                9,
                17,
                0,
                0,
                0,
                tzinfo=timezone.utc,
            )
            service.record_upload(make_payload(), make_result("NEW"))

            page = service.list_entries()

            self.assertEqual(page.total, 1)
            self.assertEqual(page.items[0].request_id, "NEW")
            self.assertEqual(
                len(list(service.images_directory.glob("*.jpg"))),
                2,
            )

    def test_enforce_retention_cleans_without_a_new_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            current_time = [
                datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc)
            ]
            service = LogService(
                logs_directory=Path(directory) / "logs",
                config_provider=lambda: AppConfig(
                    log_enabled=True,
                    log_image_storage_enabled=True,
                    log_retention_days=1,
                ),
                now_provider=lambda: current_time[0],
            )
            service.record_upload(make_payload(), make_result("OLD"))
            current_time[0] = datetime(
                2026,
                9,
                17,
                0,
                0,
                0,
                tzinfo=timezone.utc,
            )

            removed = service.enforce_retention()

            self.assertEqual(removed, 1)
            self.assertEqual(service.list_entries().total, 0)
            self.assertEqual(list(service.images_directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
