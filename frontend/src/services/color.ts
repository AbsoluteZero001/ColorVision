import { apiClient } from "./api";

import type { ApiResponse } from "@/types/api";
import type { ColorAnalysisResult, RoiCoordinates } from "@/types/color";

export async function analyzeRoi(
  image: Blob,
  roi: RoiCoordinates,
): Promise<ColorAnalysisResult> {
  const formData = new FormData();
  formData.append("image", image, "capture.jpg");
  formData.append("x", String(roi.x));
  formData.append("y", String(roi.y));
  formData.append("width", String(roi.width));
  formData.append("height", String(roi.height));

  const response = await apiClient.post<ApiResponse<ColorAnalysisResult>>(
    "/color/analyze",
    formData,
  );
  return response.data.data;
}
