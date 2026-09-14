export interface AppConfig {
  api_url: string;
  token: string;
  camera_id: string;
  auto_upload: boolean;
  mock_mode: boolean;
  timeout: number;
  port: number;
}

export type AppConfigUpdate = Partial<AppConfig>;

export interface HealthStatus {
  status: string;
  app: string;
  version: string;
  mock_mode: boolean;
  managed_runtime: boolean;
}
