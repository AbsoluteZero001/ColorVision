export interface AppConfig {
  api_url: string;
  token: string;
  camera_id: string;
  auto_upload: boolean;
  mock_mode: boolean;
  timeout: number;
  port: number;
  image_retention_days: number;
  max_image_count: number;
  log_enabled: boolean;
  log_image_storage_enabled: boolean;
  log_retention_days: number;
  max_log_count: number;
}

export type AppConfigUpdate = Partial<AppConfig>;

export interface HealthStatus {
  status: string;
  app: string;
  version: string;
  mock_mode: boolean;
  managed_runtime: boolean;
}
