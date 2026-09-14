import axios from "axios";

import type { ApiError } from "@/types/api";

export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 10_000,
});

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiError>(error)) {
    return error.response?.data?.message || error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "请求失败";
}
