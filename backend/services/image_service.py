"""Image persistence and transformation service boundary."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt


class ImageService:
    """Own image I/O and ROI cropping independently of HTTP and algorithms."""

    def save_capture(self, frame: npt.NDArray[np.uint8]) -> Path:
        raise NotImplementedError("Capture persistence is implemented in Phase 4")

    def read_image(self, path: Path) -> npt.NDArray[np.uint8]:
        raise NotImplementedError("Image reading is implemented in Phase 4")

    def crop_roi(
        self,
        image: npt.NDArray[np.uint8],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> npt.NDArray[np.uint8]:
        raise NotImplementedError("ROI cropping is implemented in Phase 5")
