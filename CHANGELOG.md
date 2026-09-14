# Changelog

## [1.2.0] - 2026-09-14

### Added

- 新增统一 Camera 生命周期和状态模型，覆盖初始化、可用、未检测到、打开失败、设备占用、断开、读取失败和 Mock 状态。
- 新增真正的 Mock Camera 帧源，支持与真实摄像头一致的拍照、预览和 ROI 颜色分析流程。
- 新增 `/api/camera/detect`、`/api/camera/reconnect` 和 `/api/camera/mock`，支持安全重新检测、断开恢复和真实/Mock 切换。
- 前端新增摄像头状态提示、重新检测、重新连接、使用 Mock 以及切回真实摄像头操作。
- 新增摄像头生命周期、无设备、设备占用、断开和 Mock 拍照测试。

### Fixed

- 修复 `/` 在 Vue 生产资源缺失时回退为 FastAPI JSON 的问题。
- 修复摄像头 `VideoCapture` 可以打开、但无法连续读取有效视频帧时仍被误判为 `available` 的问题。

### Changed

- Vue 页面启动与摄像头初始化完全解耦，Application Ready 和 Camera Unavailable 可以同时存在。
- Camera 状态统一使用稳定错误码，摄像头异常不会终止 FastAPI 或 Vue 应用。
- PyInstaller 和构建脚本会在打包前后校验 Vue `index.html` 与 `assets`，阻止生成不完整 EXE。
- 明确区分 Mock Upload 与 Mock Camera，现有 `mock_mode` 继续只控制上传行为。

### Verification

- 23 项自动化测试全部通过，包含真实摄像头打开、拍照和静态预览。
- 新增“打开成功但读取失败”“单帧后失败”“frame 为 None”“无有效帧设备扫描”等伪摄像头回归测试。
- Mock Camera、无摄像头错误模型、设备占用和断开状态均已验证。
- 开发模式和生产 EXE 的 Vue 首页、静态资源、Camera API、拍照和 Mock 切换均已验证。
- 缺少 `frontend/dist` 时，PyInstaller 构建会按预期失败并阻止生成不完整发布包。
- 物理 USB 拔插和目标公司电脑仍建议在发布前做一次现场验收。
