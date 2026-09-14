"""Color algorithm service boundary."""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt

from backend.models.color import ColorAnalysisData


class ColorService:
    """Convert ROI pixels into normalized RGB, CIELAB, and HEX values."""

    def calculate_rgb(self, roi: npt.NDArray[np.uint8]) -> tuple[int, int, int]:
        raise NotImplementedError("RGB statistics are implemented in Phase 5")

    def calculate_lab(self, rgb: tuple[int, int, int]) -> tuple[float, float, float]:
        raise NotImplementedError("CIELAB conversion is implemented in Phase 5")

    def rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        raise NotImplementedError("HEX conversion is implemented in Phase 5")

    def analyze_roi(
        self,
        image: npt.NDArray[np.uint8],
        x: int,
        y: int,
        width: int,
        height: int,
        **options: Any,
    ) -> ColorAnalysisData:
        raise NotImplementedError("ROI analysis is implemented in Phase 5")
