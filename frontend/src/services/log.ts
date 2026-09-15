import { apiClient } from "./api";

import type { ApiResponse } from "@/types/api";
import type {
  UploadLogDeleteResult,
  UploadLogPage,
} from "@/types/log";

export async function listUploadLogs(
  limit = 20,
  offset = 0,
): Promise<UploadLogPage> {
  const response = await apiClient.get<ApiResponse<UploadLogPage>>("/logs", {
    params: { limit, offset },
  });
  return response.data.data;
}

export async function deleteUploadLog(
  logId: number,
): Promise<UploadLogDeleteResult> {
  const response = await apiClient.delete<
    ApiResponse<UploadLogDeleteResult>
  >(`/logs/${logId}`);
  return response.data.data;
}

export async function clearUploadLogs(): Promise<UploadLogDeleteResult> {
  const response =
    await apiClient.delete<ApiResponse<UploadLogDeleteResult>>("/logs");
  return response.data.data;
}
