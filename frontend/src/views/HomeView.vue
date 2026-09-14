<script setup lang="ts">
import CameraView from "@/components/CameraView.vue";
import CapturePanel from "@/components/CapturePanel.vue";
import ColorResult from "@/components/ColorResult.vue";
import RoiSelector from "@/components/RoiSelector.vue";
</script>

<template>
  <div class="home-view">
    <div class="page-heading">
      <div>
        <h1>颜色采集工作台</h1>
        <p>实时采集与 ROI 颜色分析</p>
      </div>
      <span class="workflow-state">设备未连接</span>
    </div>

    <div class="workspace-grid">
      <CameraView class="camera-area" />
      <CapturePanel class="capture-area" />
      <RoiSelector class="roi-area" />
      <ColorResult class="result-area" />
    </div>
  </div>
</template>

<style scoped>
.workflow-state {
  padding: 7px 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-muted);
  background: var(--surface);
  font-size: 0.82rem;
  white-space: nowrap;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.65fr);
  gap: 18px;
  align-items: start;
}

.camera-area {
  grid-column: 1;
}

.capture-area {
  grid-column: 2;
}

.roi-area {
  grid-column: 1;
}

.result-area {
  grid-column: 2;
}

@media (max-width: 960px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .camera-area,
  .capture-area,
  .roi-area,
  .result-area {
    grid-column: 1;
  }
}
</style>
