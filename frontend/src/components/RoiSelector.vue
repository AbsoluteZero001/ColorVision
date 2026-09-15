<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

import type { RoiCoordinates } from "@/types/color";

const props = withDefaults(
  defineProps<{
    imageUrl?: string | null;
    disabled?: boolean;
    analysisPending?: boolean;
    uploading?: boolean;
  }>(),
  {
    imageUrl: null,
    disabled: false,
    analysisPending: false,
    uploading: false,
  },
);

const emit = defineEmits<{
  change: [roi: RoiCoordinates | null];
  confirm: [roi: RoiCoordinates];
}>();

const imageElement = ref<HTMLImageElement | null>(null);
const naturalWidth = ref(0);
const naturalHeight = ref(0);
const roi = ref<RoiCoordinates | null>(null);
const dragging = ref(false);
const roiError = ref("");

let dragStart: { x: number; y: number } | null = null;

const hasImage = computed(() => Boolean(props.imageUrl));
const interactionLocked = computed(
  () => props.disabled || props.analysisPending || props.uploading,
);
const canConfirm = computed(
  () =>
    Boolean(roi.value) &&
    (roi.value?.width ?? 0) >= 2 &&
    (roi.value?.height ?? 0) >= 2 &&
    !interactionLocked.value,
);

const selectionStyle = computed(() => {
  if (!roi.value || naturalWidth.value === 0 || naturalHeight.value === 0) {
    return {};
  }
  return {
    left: `${(roi.value.x / naturalWidth.value) * 100}%`,
    top: `${(roi.value.y / naturalHeight.value) * 100}%`,
    width: `${(roi.value.width / naturalWidth.value) * 100}%`,
    height: `${(roi.value.height / naturalHeight.value) * 100}%`,
  };
});

const roiText = computed(() => {
  if (!roi.value) {
    return "x — · y — · w — · h —";
  }
  const { x, y, width, height } = roi.value;
  return `x ${x} · y ${y} · w ${width} · h ${height}`;
});

function handleImageLoad(): void {
  const element = imageElement.value;
  if (!element) {
    return;
  }
  naturalWidth.value = element.naturalWidth;
  naturalHeight.value = element.naturalHeight;
  resetRoi();
}

function beginSelection(event: MouseEvent): void {
  if (
    interactionLocked.value ||
    !imageElement.value ||
    !naturalWidth.value ||
    !naturalHeight.value ||
    event.button !== 0
  ) {
    return;
  }

  event.preventDefault();
  const point = toOriginalCoordinates(event);
  dragStart = point;
  dragging.value = true;
  roiError.value = "";
  roi.value = { x: point.x, y: point.y, width: 0, height: 0 };
  emit("change", roi.value);

  window.addEventListener("mousemove", updateSelection);
  window.addEventListener("mouseup", finishSelection);
}

function updateSelection(event: MouseEvent): void {
  if (!dragging.value || !dragStart) {
    return;
  }
  const point = toOriginalCoordinates(event);
  roi.value = {
    x: Math.min(dragStart.x, point.x),
    y: Math.min(dragStart.y, point.y),
    width: Math.abs(point.x - dragStart.x),
    height: Math.abs(point.y - dragStart.y),
  };
  emit("change", roi.value);
}

function finishSelection(): void {
  if (!dragging.value) {
    return;
  }
  dragging.value = false;
  removeWindowListeners();
  if (!roi.value || roi.value.width < 2 || roi.value.height < 2) {
    roi.value = null;
    roiError.value = "请拖动选择有效的 ROI 区域";
    emit("change", null);
  }
}

function toOriginalCoordinates(event: MouseEvent): { x: number; y: number } {
  const element = imageElement.value;
  if (!element || !naturalWidth.value || !naturalHeight.value) {
    return { x: 0, y: 0 };
  }

  const bounds = element.getBoundingClientRect();
  const scaleX = naturalWidth.value / bounds.width;
  const scaleY = naturalHeight.value / bounds.height;
  const x = Math.round((event.clientX - bounds.left) * scaleX);
  const y = Math.round((event.clientY - bounds.top) * scaleY);

  return {
    x: Math.min(Math.max(x, 0), naturalWidth.value),
    y: Math.min(Math.max(y, 0), naturalHeight.value),
  };
}

function resetRoi(): void {
  dragging.value = false;
  dragStart = null;
  roi.value = null;
  roiError.value = "";
  removeWindowListeners();
  emit("change", null);
}

function confirmRoi(): void {
  if (!canConfirm.value || !roi.value) {
    roiError.value = "ROI 区域过小或尚不可用";
    return;
  }
  roiError.value = "";
  emit("confirm", { ...roi.value });
}

function removeWindowListeners(): void {
  window.removeEventListener("mousemove", updateSelection);
  window.removeEventListener("mouseup", finishSelection);
}

watch(
  () => props.imageUrl,
  () => {
    naturalWidth.value = 0;
    naturalHeight.value = 0;
    resetRoi();
  },
);

onBeforeUnmount(removeWindowListeners);
</script>

<template>
  <section class="panel roi-panel">
    <div class="panel-header">
      <h2>ROI 框选</h2>
      <span class="muted">{{ roiText }}</span>
    </div>
    <div class="roi-stage">
      <div v-if="!hasImage" class="roi-empty">
        <span class="roi-corners" aria-hidden="true"></span>
        <strong>尚未拍摄图片</strong>
        <small>等待拍摄结果</small>
      </div>
      <template v-else>
        <div class="image-frame">
          <img
            ref="imageElement"
            class="capture-image"
            :src="imageUrl ?? ''"
            alt="待分析拍摄图片"
            draggable="false"
            @load="handleImageLoad"
            @mousedown="beginSelection"
          />
          <div
            v-if="roi && roi.width > 0 && roi.height > 0"
            class="roi-selection"
            :style="selectionStyle"
            aria-hidden="true"
          ></div>
        </div>
        <div class="roi-actions">
          <p v-if="roiError" class="roi-error" role="status">{{ roiError }}</p>
          <div class="roi-buttons">
            <button
              class="button secondary"
              type="button"
              :disabled="interactionLocked"
              @click="resetRoi"
            >
              重置
            </button>
            <button
              class="button"
              type="button"
              :disabled="!canConfirm || analysisPending"
              @click="confirmRoi"
            >
              {{ analysisPending ? "识别中" : "识别颜色" }}
            </button>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.roi-stage {
  display: grid;
  place-items: center;
  min-height: 320px;
  padding: 24px;
  background:
    linear-gradient(45deg, #edf1f0 25%, transparent 25%),
    linear-gradient(-45deg, #edf1f0 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #edf1f0 75%),
    linear-gradient(-45deg, transparent 75%, #edf1f0 75%);
  background-color: #f7f9f8;
  background-position:
    0 0,
    0 10px,
    10px -10px,
    -10px 0;
  background-size: 20px 20px;
}

.image-frame {
  position: relative;
  display: inline-block;
  max-width: 100%;
  line-height: 0;
  cursor: crosshair;
  user-select: none;
}

.capture-image {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 68vh;
}

.roi-selection {
  position: absolute;
  border: 2px solid #40d4c4;
  background: rgba(64, 212, 196, 0.16);
  box-shadow:
    0 0 0 1px rgba(23, 32, 31, 0.7),
    inset 0 0 0 1px rgba(255, 255, 255, 0.45);
  pointer-events: none;
}

.roi-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  width: 100%;
  margin-top: 16px;
}

.roi-buttons {
  display: flex;
  gap: 10px;
  margin-left: auto;
}

.roi-error {
  margin: 0;
  color: var(--danger);
  font-size: 0.84rem;
}

.roi-empty {
  display: grid;
  justify-items: center;
  color: var(--text-muted);
  text-align: center;
}

.roi-empty strong {
  margin-top: 18px;
  color: var(--text);
}

.roi-empty small {
  margin-top: 6px;
}

.roi-corners {
  position: relative;
  width: 82px;
  height: 64px;
  border: 1px dashed #95a6a2;
}

.roi-corners::before,
.roi-corners::after {
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: var(--accent);
  border-style: solid;
  content: "";
}

.roi-corners::before {
  top: -2px;
  left: -2px;
  border-width: 3px 0 0 3px;
}

.roi-corners::after {
  right: -2px;
  bottom: -2px;
  border-width: 0 3px 3px 0;
}

@media (max-width: 560px) {
  .roi-stage {
    padding: 12px;
  }

  .roi-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .roi-buttons {
    width: 100%;
  }

  .roi-buttons .button {
    flex: 1;
  }
}
</style>
