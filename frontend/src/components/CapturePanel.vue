<script setup lang="ts">
withDefaults(
  defineProps<{
    cameraReady?: boolean;
    hasCapture?: boolean;
    capturing?: boolean;
    locked?: boolean;
  }>(),
  {
    cameraReady: false,
    hasCapture: false,
    capturing: false,
    locked: false,
  },
);

const emit = defineEmits<{
  capture: [];
  retake: [];
}>();
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <h2>拍摄控制</h2>
      <span class="muted">{{ cameraReady ? "摄像头已连接" : "等待摄像头" }}</span>
    </div>
    <div class="panel-body capture-actions">
      <button
        class="button"
        type="button"
        :disabled="!cameraReady || capturing || locked"
        @click="emit('capture')"
      >
        {{ capturing ? "拍摄中" : "拍照" }}
      </button>
      <button
        class="button secondary"
        type="button"
        :disabled="!hasCapture || capturing || locked"
        @click="emit('retake')"
      >
        重新拍摄
      </button>
    </div>
  </section>
</template>

<style scoped>
.capture-actions {
  display: flex;
  gap: 10px;
}

@media (max-width: 520px) {
  .capture-actions {
    flex-direction: column;
  }
}
</style>
