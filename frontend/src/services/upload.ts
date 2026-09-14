import { apiClient } from "./api";

import type { ApiResponse } from "@/types/api";
import type { ColorAnalysisResult } from "@/types/color";

export interface UploadPayload {
  originalImage: Blob;
  roiImage: Blob;
  result: ColorAnalysisResult;
  cameraId: string;
  timestamp: string;
}

export async function uploadResult(
  payload: UploadPayload,
): Promise<Record<string, string>> {
  const formData = new FormData();
  formData.append("original_image", payload.originalImage, "original.jpg");
  formData.append("roi_image", payload.roiImage, "roi.jpg");
  formData.append("rgb", JSON.stringify(payload.result.rgb));
  formData.append("lab", JSON.stringify(payload.result.lab));
  formData.append("hex", payload.result.hex);
  formData.append("camera_id", payload.cameraId);
  formData.append("timestamp", payload.timestamp);

  const response = await apiClient.post<ApiResponse<Record<string, string>>>(
    "/upload",
    formData,
  );
  return response.data.data;
}
