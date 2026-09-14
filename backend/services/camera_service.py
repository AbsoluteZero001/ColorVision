"""Camera hardware service boundary."""

from __future__ import annotations

from backend.models.camera import CameraInfo, CameraStatusData


class CameraService:
    """Own camera discovery, lifecycle, frame access, and capture behavior.

    The implementation intentionally remains in this service so HTTP routes do
    not become coupled to OpenCV or a specific camera index.
    """

    def list_cameras(self) -> list[CameraInfo]:
        raise NotImplementedError("Camera enumeration is implemented in Phase 3")

    def open_camera(self, index: int) -> CameraStatusData:
        raise NotImplementedError("Camera opening is implemented in Phase 3")

    def close_camera(self) -> CameraStatusData:
        raise NotImplementedError("Camera closing is implemented in Phase 3")

    def get_status(self) -> CameraStatusData:
        raise NotImplementedError("Camera status is implemented in Phase 3")

    def read_frame(self) -> object:
        raise NotImplementedError("Frame access is implemented in Phase 3")
