<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { apiClient, getApiErrorMessage } from "@/services/api";
import type { ApiResponse } from "@/types/api";
import type { AppConfig } from "@/types/config";

const form = reactive<AppConfig>({
  api_url: "",
  token: "",
  camera_id: "",
  auto_upload: false,
  mock_mode: true,
  request_timeout_seconds: 10,
});

const loading = ref(true);
const saving = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");

async function loadConfig(): Promise<void> {
  loading.value = true;
  try {
    const response =
      await apiClient.get<ApiResponse<AppConfig>>("/config");
    Object.assign(form, response.data.data);
  } catch (error) {
    messageType.value = "error";
    message.value = getApiErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

async function saveConfig(): Promise<void> {
  saving.value = true;
  message.value = "";
  try {
    const response = await apiClient.put<ApiResponse<AppConfig>>(
      "/config",
      form,
    );
    Object.assign(form, response.data.data);
    messageType.value = "success";
    message.value = "配置已保存";
  } catch (error) {
    messageType.value = "error";
    message.value = getApiErrorMessage(error);
  } finally {
    saving.value = false;
  }
}

onMounted(loadConfig);
</script>

<template>
  <div class="settings-view">
    <div class="page-heading">
      <div>
        <h1>本地设置</h1>
        <p>上传、设备与运行模式参数</p>
      </div>
    </div>

    <form class="panel settings-panel" @submit.prevent="saveConfig">
      <div class="settings-grid">
        <label class="field field-wide">
          <span>API URL</span>
          <input
            v-model.trim="form.api_url"
            type="url"
            required
            autocomplete="off"
            :disabled="loading || saving"
            placeholder="http://127.0.0.1:9000/api/color"
          />
        </label>

        <label class="field">
          <span>Token</span>
          <input
            v-model="form.token"
            type="password"
            autocomplete="off"
            :disabled="loading || saving"
          />
        </label>

        <label class="field">
          <span>Camera ID</span>
          <input
            v-model.trim="form.camera_id"
            type="text"
            required
            :disabled="loading || saving"
            placeholder="CAM-001"
          />
        </label>

        <label class="field">
          <span>API 超时（秒）</span>
          <input
            v-model.number="form.request_timeout_seconds"
            type="number"
            min="0.1"
            max="120"
            step="0.1"
            required
            :disabled="loading || saving"
          />
        </label>

        <label class="toggle-row">
          <span>
            <strong>自动上传</strong>
            <small>颜色分析完成后提交结果</small>
          </span>
          <input
            v-model="form.auto_upload"
            type="checkbox"
            :disabled="loading || saving"
          />
        </label>

        <label class="toggle-row">
          <span>
            <strong>Mock 模式</strong>
            <small>使用本地模拟对象存储上传响应</small>
          </span>
          <input
            v-model="form.mock_mode"
            type="checkbox"
            :disabled="loading || saving"
          />
        </label>
      </div>

      <div class="settings-footer">
        <p
          v-if="message"
          class="form-message"
          :class="messageType"
          role="status"
        >
          {{ message }}
        </p>
        <button class="button" type="submit" :disabled="loading || saving">
          {{ saving ? "保存中" : "保存配置" }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.settings-view {
  max-width: 920px;
}

.settings-panel {
  padding: clamp(18px, 3vw, 30px);
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.field {
  display: grid;
  gap: 8px;
}

.field-wide {
  grid-column: 1 / -1;
}

.field > span {
  color: var(--text-muted);
  font-size: 0.84rem;
}

.field input {
  width: 100%;
  min-height: 42px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  outline: none;
  color: var(--text);
  background: var(--surface-muted);
}

.field input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(14, 118, 110, 0.12);
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 76px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-muted);
}

.toggle-row span {
  display: grid;
  gap: 4px;
}

.toggle-row strong {
  font-size: 0.9rem;
}

.toggle-row small {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.toggle-row input {
  width: 38px;
  height: 20px;
  accent-color: var(--accent);
}

.settings-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.form-message {
  margin: 0;
  font-size: 0.88rem;
}

.form-message.success {
  color: var(--success);
}

.form-message.error {
  color: var(--danger);
}

@media (max-width: 680px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .field-wide {
    grid-column: 1;
  }
}
</style>
