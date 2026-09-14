<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiClient, getApiErrorMessage } from "@/services/api";
import type { ApiResponse } from "@/types/api";
import type { HealthStatus } from "@/types/config";

type ConnectionState = "checking" | "online" | "offline";

const state = ref<ConnectionState>("checking");
const detail = ref("正在检查");

const label = computed(() => {
  if (state.value === "online") {
    return "服务在线";
  }
  if (state.value === "offline") {
    return "服务离线";
  }
  return detail.value;
});

async function refresh(): Promise<void> {
  state.value = "checking";
  detail.value = "正在检查";
  try {
    const response =
      await apiClient.get<ApiResponse<HealthStatus>>("/health");
    detail.value = `v${response.data.data.version}`;
    state.value = "online";
  } catch (error) {
    detail.value = getApiErrorMessage(error);
    state.value = "offline";
  }
}

onMounted(refresh);
</script>

<template>
  <button
    class="api-status"
    :class="state"
    type="button"
    :title="detail"
    @click="refresh"
  >
    <span class="status-dot" aria-hidden="true"></span>
    {{ label }}
  </button>
</template>

<style scoped>
.api-status {
  display: inline-flex;
  align-items: center;
  justify-self: end;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-muted);
  background: var(--surface);
  cursor: pointer;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #98a3a1;
}

.api-status.online .status-dot {
  background: var(--success);
  box-shadow: 0 0 0 4px rgba(36, 122, 85, 0.12);
}

.api-status.offline .status-dot {
  background: var(--danger);
  box-shadow: 0 0 0 4px rgba(182, 65, 55, 0.12);
}

.api-status.checking .status-dot {
  background: var(--warning);
}
</style>
