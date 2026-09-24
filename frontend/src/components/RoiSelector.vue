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

type DragMode =
  | "create"
  | "move"
  | "n"
  | "s"
  | "e"
  | "w"
  | "ne"
  | "nw"
  | "se"
  | "sw";

const MIN_ROI_SIZE = 4;
const HIT_TOLERANCE_PX = 20;

let dragMode: DragMode | null = null;
let dragStart: { x: number; y: number } | null = null;
let originRoi: RoiCoordinates | null = null;

const hasImage = computed(() => Boolean(props.imageUrl));
const interactionLocked = computed(
  () => props.disabled || props.analysisPending || props.uploading,
);
const canConfirm = computed(
  () =>
    Boolean(roi.value) &&
    (roi.value?.width ?? 0) >= MIN_ROI_SIZE &&
    (roi.value?.height ?? 0) >= MIN_ROI_SIZE &&
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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function hitToleranceNatural(): number {
  const element = imageElement.value;
  if (!element || !naturalWidth.value) {
    return HIT_TOLERANCE_PX;
  }
  const bounds = element.getBoundingClientRect();
  if (!bounds.width) {
    return HIT_TOLERANCE_PX;
  }
  return HIT_TOLERANCE_PX * (naturalWidth.value / bounds.width);
}

function hitTest(
  point: { x: number; y: number },
  current: RoiCoordinates,
): DragMode | null {
  const tol = hitToleranceNatural();
  const left = current.x;
  const top = current.y;
  const right = current.x + current.width;
  const bottom = current.y + current.height;

  const nearLeft = Math.abs(point.x - left) <= tol;
  const nearRight = Math.abs(point.x - right) <= tol;
  const nearTop = Math.abs(point.y - top) <= tol;
  const nearBottom = Math.abs(point.y - bottom) <= tol;
  const withinX = point.x >= left - tol && point.x <= right + tol;
  const withinY = point.y >= top - tol && point.y <= bottom + tol;
  const inside =
    point.x >= left && point.x <= right && point.y >= top && point.y <= bottom;

  if (nearLeft && nearTop) {
    return "nw";
  }
  if (nearRight && nearTop) {
    return "ne";
  }
  if (nearLeft && nearBottom) {
    return "sw";
  }
  if (nearRight && nearBottom) {
    return "se";
  }
  if (nearLeft && withinY) {
    return "w";
  }
  if (nearRight && withinY) {
    return "e";
  }
  if (nearTop && withinX) {
    return "n";
  }
  if (nearBottom && withinX) {
    return "s";
  }
  if (inside) {
    return "move";
  }
  return null;
}

function beginSelection(event: PointerEvent): void {
  if (
    interactionLocked.value ||
    !imageElement.value ||
    !naturalWidth.value ||
    !naturalHeight.value ||
    !event.isPrimary ||
    (event.pointerType === "mouse" && event.button !== 0)
  ) {
    return;
  }

  event.preventDefault();
  imageElement.value.setPointerCapture(event.pointerId);
  const point = toOriginalCoordinates(event);
  dragStart = point;
  dragging.value = true;
  roiError.value = "";

  const current = roi.value;
  const mode = current ? hitTest(point, current) : null;
  if (current && mode) {
    dragMode = mode;
    originRoi = { ...current };
  } else {
    dragMode = "create";
    originRoi = null;
    roi.value = { x: point.x, y: point.y, width: 0, height: 0 };
  }
  emit("change", roi.value);
}

function updateSelection(event: PointerEvent): void {
  if (!dragging.value || !dragStart || !dragMode || !event.isPrimary) {
    return;
  }
  const point = toOriginalCoordinates(event);
  if (dragMode === "create") {
    roi.value = {
      x: Math.min(dragStart.x, point.x),
      y: Math.min(dragStart.y, point.y),
      width: Math.abs(point.x - dragStart.x),
      height: Math.abs(point.y - dragStart.y),
    };
  } else if (dragMode === "move" && originRoi) {
    const dx = point.x - dragStart.x;
    const dy = point.y - dragStart.y;
    roi.value = {
      ...originRoi,
      x: clamp(
        Math.round(originRoi.x + dx),
        0,
        naturalWidth.value - originRoi.width,
      ),
      y: clamp(
        Math.round(originRoi.y + dy),
        0,
        naturalHeight.value - originRoi.height,
      ),
    };
  } else if (originRoi) {
    roi.value = resizeRoi(dragMode, point);
  }
  emit("change", roi.value);
}

function resizeRoi(
  mode: DragMode,
  point: { x: number; y: number },
): RoiCoordinates {
  const origin = originRoi;
  if (!origin) {
    return { x: point.x, y: point.y, width: 0, height: 0 };
  }
  let left = origin.x;
  let top = origin.y;
  let right = origin.x + origin.width;
  let bottom = origin.y + origin.height;

  if (mode.includes("w")) {
    left = clamp(point.x, 0, right - MIN_ROI_SIZE);
  }
  if (mode.includes("e")) {
    right = clamp(point.x, left + MIN_ROI_SIZE, naturalWidth.value);
  }
  if (mode.includes("n")) {
    top = clamp(point.y, 0, bottom - MIN_ROI_SIZE);
  }
  if (mode.includes("s")) {
    bottom = clamp(point.y, top + MIN_ROI_SIZE, naturalHeight.value);
  }

  return { x: left, y: top, width: right - left, height: bottom - top };
}

function finishSelection(event: PointerEvent): void {
  if (!dragging.value) {
    return;
  }
  const mode = dragMode;
  dragging.value = false;
  dragMode = null;
  dragStart = null;
  originRoi = null;
  releasePointer(event);
  if (
    mode === "create" &&
    (!roi.value ||
      roi.value.width < MIN_ROI_SIZE ||
      roi.value.height < MIN_ROI_SIZE)
  ) {
    roi.value = null;
    roiError.value = "请拖动选择有效的 ROI 区域";
    emit("change", null);
  }
}

function cancelSelection(event: PointerEvent): void {
  if (!dragging.value) {
    return;
  }
  dragging.value = false;
  if (dragMode && dragMode !== "create" && originRoi) {
    roi.value = { ...originRoi };
    emit("change", roi.value);
  } else {
    roi.value = null;
    emit("change", null);
  }
  dragMode = null;
  dragStart = null;
  originRoi = null;
  releasePointer(event);
}

function releasePointer(event: PointerEvent): void {
  const element = imageElement.value;
  if (element && element.hasPointerCapture(event.pointerId)) {
    element.releasePointerCapture(event.pointerId);
  }
}

function toOriginalCoordinates(event: PointerEvent): { x: number; y: number } {
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
  dragMode = null;
  dragStart = null;
  originRoi = null;
  roi.value = null;
  roiError.value = "";
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

watch(
  () => props.imageUrl,
  () => {
    naturalWidth.value = 0;
    naturalHeight.value = 0;
    resetRoi();
  },
);

onBeforeUnmount(() => {
  dragging.value = false;
  dragMode = null;
  dragStart = null;
  originRoi = null;
});
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
            @pointerdown="beginSelection"
            @pointermove="updateSelection"
            @pointerup="finishSelection"
            @pointercancel="cancelSelection"
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
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}

.capture-image {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 68vh;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
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
