import axios from "axios";

import type { ApiError } from "@/types/api";

export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 10_000,
});

export function getApiErrorMessage(error: unknown): string {
  return getApiErrorDetails(error).message;
}

export function getApiErrorDetails(error: unknown): {
  message: string;
  code: string | null;
} {
  if (axios.isAxiosError<ApiError>(error)) {
    return {
      message: error.response?.data?.message || error.message,
      code: error.response?.data?.code || null,
    };
  }
  if (error instanceof Error) {
    return { message: error.message, code: null };
  }
  return { message: "请求失败", code: null };
}
