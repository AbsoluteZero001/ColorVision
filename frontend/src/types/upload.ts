export interface UploadResult {
  success: boolean;
  message: string;
  request_id: string;
  mode: "mock" | "api";
  target_url: string | null;
  upstream_status_code: number | null;
  upstream_response: Record<string, unknown> | null;
}
