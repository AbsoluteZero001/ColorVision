import assert from "node:assert/strict";
import test from "node:test";

import {
  createRecognitionSnapshot,
  createUploadSnapshot,
} from "../src/services/workflowSnapshots.ts";

function waitForPendingOperation() {
  return new Promise((resolve) => setTimeout(resolve, 10));
}

test("recognition keeps the ROI captured when the request starts", async () => {
  const sourceRoi = { x: 10, y: 20, width: 30, height: 40 };
  const snapshot = createRecognitionSnapshot(
    new Blob(["capture"], { type: "image/jpeg" }),
    sourceRoi,
  );
  const pendingRequest = waitForPendingOperation().then(() => snapshot);

  sourceRoi.x = 999;
  sourceRoi.width = 1;

  const completedRequest = await pendingRequest;
  assert.deepEqual(completedRequest.roi, {
    x: 10,
    y: 20,
    width: 30,
    height: 40,
  });
});

test("upload keeps image, result, and config captured at request start", async () => {
  const image = new Blob(["original"], { type: "image/jpeg" });
  const capture = {
    image_path: "captures/original.jpg",
    image_url: "/media/captures/original.jpg",
    captured_at: "2026-09-15T10:00:00+08:00",
  };
  const result = {
    rgb: { r: 120, g: 35, b: 40 },
    lab: { l: 27.84, a: 37, b: 18 },
    hex: "#782328",
    roi: { x: 10, y: 20, width: 60, height: 40 },
  };
  const config = {
    api_url: "http://127.0.0.1:9000/api/color",
    token: "",
    camera_id: "CAM-ORIGINAL",
    auto_upload: false,
    mock_mode: true,
    timeout: 10,
    port: 8000,
    image_retention_days: 0,
    max_image_count: 0,
  };
  const snapshot = createUploadSnapshot(image, capture, result, config);
  const pendingRequest = waitForPendingOperation().then(() => snapshot);

  result.rgb.r = 1;
  result.roi.x = 999;
  config.camera_id = "CAM-CHANGED";
  config.timeout = 120;
  capture.captured_at = "changed";

  const completedRequest = await pendingRequest;
  assert.equal(completedRequest.originalImage, image);
  assert.equal(completedRequest.result.rgb.r, 120);
  assert.deepEqual(completedRequest.result.roi, {
    x: 10,
    y: 20,
    width: 60,
    height: 40,
  });
  assert.equal(completedRequest.cameraId, "CAM-ORIGINAL");
  assert.equal(completedRequest.timestamp, "2026-09-15T10:00:00+08:00");
  assert.equal(completedRequest.timeoutMs, 12_000);
});
