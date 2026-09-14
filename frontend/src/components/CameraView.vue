<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import {
  closeCamera,
  getCameraStatus,
  listCameras,
  openCamera,
} from "@/services/camera";
import { getApiErrorMessage } from "@/services/api";
import type { CameraInfo, CameraStatus } from "@/types/camera";

const props = withDefaults(
  defineProps<{
    frozen?: boolean;
    capturedImageUrl?: string | null;
  }>(),
  {
    frozen: false,
    capturedImageUrl: null,
  },
);

const emit = defineEmits<{
  statusChange: [status: CameraStatus];
  error: [message: string];
}>();

const cameras = ref<CameraInfo[]>([]);
const selectedIndex = ref<number | null>(null);
const status = ref<CameraStatus>({
  opened: false,
  index: null,
  name: null,
  available: false,
  width: null,
  height: null,
  fps: null,
});
const busy = ref(false);
const streamSession = ref(0);
const streamFailed = ref(false);

const streamUrl = computed(() => {
  if (!status.value.opened || props.frozen || streamFailed.value) {
    return "";
  }
  return `/api/camera/stream?session=${streamSession.value}`;
});

const resolutionText = computed(() => {
  if (!status.value.width || !status.value.height) {
    return status.value.opened ? "分辨率读取中" : "未连接";
  }
  return `${status.value.width} × ${status.value.height}`;
});

const displayImageUrl = computed(() => {
  if (props.frozen && props.capturedImageUrl) {
    return props.capturedImageUrl;
  }
  return streamUrl.value;
});

function updateStatus(nextStatus: CameraStatus): void {
  status.value = nextStatus;
  if (nextStatus.opened) {
    selectedIndex.value = nextStatus.index;
    streamFailed.value = false;
    streamSession.value += 1;
  }
  emit("statusChange", nextStatus);
}

async function refreshCameras(): Promise<void> {
  busy.value = true;
  try {
    const currentStatus = await getCameraStatus();
    const listed = await listCameras();
    cameras.value = listed.cameras;

    if (currentStatus.opened) {
      updateStatus(currentStatus);
      return;
    }

    const firstAvailable = cameras.value.find((camera) => camera.available);
    if (!firstAvailable) {
      updateStatus(currentStatus);
      emit("error", "未检测到可用摄像头");
      return;
    }

    selectedIndex.value = firstAvailable.index;
    await openSelected();
  } catch (error) {
    emit("error", getApiErrorMessage(error));
  } finally {
    busy.value = false;
  }
}

async function openSelected(): Promise<void> {
  if (selectedIndex.value === null) {
    return;
  }

  busy.value = true;
  try {
    const nextStatus = await openCamera(selectedIndex.value);
    updateStatus(nextStatus);
  } catch (error) {
    emit("error", getApiErrorMessage(error));
  } finally {
    busy.value = false;
  }
}

async function closeSelected(): Promise<void> {
  busy.value = true;
  try {
    const nextStatus = await closeCamera();
    streamFailed.value = false;
    updateStatus(nextStatus);
  } catch (error) {
    emit("error", getApiErrorMessage(error));
  } finally {
    busy.value = false;
  }
}

function restartPreview(): void {
  streamFailed.value = false;
  streamSession.value += 1;
}

function handleStreamError(): void {
  if (!status.value.opened || props.frozen) {
    return;
  }
  streamFailed.value = true;
  emit("error", "实时画面连接中断");
}

onMounted(refreshCameras);
onBeforeUnmount(() => {
  if (status.value.opened) {
    void closeCamera();
  }
});

defineExpose({
  restartPreview,
  closeSelected,
});
</script>

<template>
  <section class="panel camera-panel">
    <div class="panel-header camera-toolbar">
      <div>
        <h2>实时画面</h2>
        <span class="muted">{{ resolutionText }}</span>
      </div>
      <div class="camera-controls">
        <select
          v-model="selectedIndex"
          :disabled="busy || status.opened || cameras.length === 0"
          aria-label="摄像头"
        >
          <option
            v-for="camera in cameras"
            :key="camera.index"
            :value="camera.index"
          >
            {{ camera.name }}
          </option>
          <option v-if="cameras.length === 0" :value="null">未检测到设备</option>
        </select>
        <button
          v-if="!status.opened"
          class="button compact"
          type="button"
          :disabled="busy || selectedIndex === null"
          @click="openSelected"
        >
          {{ busy ? "连接中" : "打开" }}
        </button>
        <button
          v-else
          class="button secondary compact"
          type="button"
          :disabled="busy"
          @click="closeSelected"
        >
          关闭
        </button>
      </div>
    </div>

    <div class="camera-stage" aria-label="摄像头预览区域">
      <img
        v-if="displayImageUrl"
        :src="displayImageUrl"
        class="camera-image"
        alt="摄像头实时画面"
        @error="handleStreamError"
      />
      <div v-else class="camera-empty">
        <span>{{ props.frozen ? "CAPTURE" : "LIVE" }}</span>
        <strong>{{ props.frozen ? "已冻结拍摄画面" : "等待摄像头连接" }}</strong>
        <button
          v-if="streamFailed && status.opened"
          class="button compact"
          type="button"
          @click="restartPreview"
        >
          重连画面
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.camera-toolbar {
  align-items: center;
}

.camera-toolbar > div:first-child {
  display: grid;
  gap: 3px;
}

.camera-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.camera-controls select {
  min-width: 150px;
  min-height: 36px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  background: var(--surface);
}

.compact {
  min-height: 36px;
  padding: 0 13px;
}

.camera-stage {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 360px;
  overflow: hidden;
  background:
    linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    #17201f;
  background-size: 28px 28px;
}

.camera-image {
  display: block;
  width: 100%;
  max-height: 68vh;
  object-fit: contain;
}

.camera-empty {
  display: grid;
  gap: 12px;
  justify-items: center;
  color: #d8e3e1;
}

.camera-empty span {
  color: #69d2c5;
  font-size: 0.72rem;
}

.camera-empty strong {
  font-size: 1rem;
}

@media (max-width: 620px) {
  .camera-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .camera-controls {
    width: 100%;
  }

  .camera-controls select {
    flex: 1;
    min-width: 0;
  }
}

@media (max-width: 760px) {
  .camera-stage {
    min-height: 260px;
  }
}
</style>
