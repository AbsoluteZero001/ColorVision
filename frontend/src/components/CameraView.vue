<template>
  <section class="panel camera-panel">
    <div class="panel-header">
      <h2>实时画面</h2>
      <span class="muted">未选择设备</span>
    </div>
    <div class="camera-stage" aria-label="摄像头预览区域">
      <div class="target-frame" aria-hidden="true"></div>
      <div class="camera-empty">
        <span>LIVE</span>
        <strong>等待摄像头连接</strong>
      </div>
    </div>
  </section>
</template>

<style scoped>
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

.camera-stage::after {
  position: absolute;
  inset: 20px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  content: "";
  pointer-events: none;
}

.target-frame {
  width: min(240px, 42vw);
  aspect-ratio: 4 / 3;
  border: 1px solid rgba(74, 208, 194, 0.55);
}

.target-frame::before,
.target-frame::after {
  position: absolute;
  width: 22px;
  height: 22px;
  border-color: #69d2c5;
  border-style: solid;
  content: "";
}

.target-frame::before {
  margin: -1px 0 0 -1px;
  border-width: 2px 0 0 2px;
}

.target-frame::after {
  margin: 139px 0 0 217px;
  border-width: 0 2px 2px 0;
}

.camera-empty {
  position: absolute;
  bottom: 42px;
  display: grid;
  gap: 5px;
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

@media (max-width: 760px) {
  .camera-stage {
    min-height: 260px;
  }

  .target-frame::after {
    display: none;
  }
}
</style>
