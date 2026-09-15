# Changelog

## [1.3.0] - 2026-09-15

### Changed

- 将应用版本统一升级为 V1.3.0。
- 颜色识别结果预览改为单一纯色块，移除棋盘格小矩形背景。
- 启动时比较运行中版本，避免新版本误连接旧版本进程。
- 构建产物改在隔离 staging 目录生成，保留已有 `config/` 和 `data/`。
- 自动生成包含 Windows 版本资源的 EXE 和版本化 ZIP。
- 新增拍摄图片保留天数和最大数量配置，默认关闭自动清理。

### Fixed

- 修复识别和上传过程中修改页面状态可能导致结果与请求数据不一致的问题。
- 修复多摄像头枚举只返回第一台设备的问题。
- 修复空白或为空的 `camera_id` 更新返回 500 的问题，现在返回 422。
- 区分摄像头普通打开失败、设备占用和驱动异常。

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
- 修复 Windows 无摄像头时占位视频源返回全黑帧仍被误判为摄像头已连接的问题。

### Changed

- 用户可见名称统一为“颜色识别系统”，版本保持 V1.2.0；EXE 文件名和既有数据目录保持兼容。
- Vue 页面启动与摄像头初始化完全解耦，Application Ready 和 Camera Unavailable 可以同时存在。
- Camera 状态统一使用稳定错误码，摄像头异常不会终止 FastAPI 或 Vue 应用。
- PyInstaller 和构建脚本会在打包前后校验 Vue `index.html` 与 `assets`，阻止生成不完整 EXE。
- 明确区分 Mock Upload 与 Mock Camera，现有 `mock_mode` 继续只控制上传行为。
- Windows 摄像头后端按 DSHOW 后 MSMF 的顺序探测，避免无设备扫描回退到 FFmpeg 索引路径。
- ROI 颜色采样改为暗亮过滤、median/MAD 离群点剔除和稳健均值，提高重复测量一致性。
- sRGB 到 CIELAB 改用 float32 标准 D65 转换，避免 OpenCV uint8 LAB 的量化偏移。

### Verification

- 31 项自动化测试执行完成，30 项通过，1 项物理摄像头测试在设备不可用时跳过。
- 新增“打开成功但读取失败”“单帧后失败”“frame 为 None”“全黑帧”“无有效帧设备扫描”等伪摄像头回归测试。
- 新增标准 sRGB/D65 CIELAB 基准、局部高光稳健采样、分辨率元数据和 PyInstaller 路径测试。
- Mock Camera、无摄像头错误模型、设备占用和断开状态均已验证。
- 开发模式和生产 EXE 的 Vue 首页、静态资源、Camera API、拍照和 Mock 切换均已验证。
- 缺少 `frontend/dist` 时，PyInstaller 构建会按预期失败并阻止生成不完整发布包。
- 物理 USB 拔插和目标公司电脑仍建议在发布前做一次现场验收。
