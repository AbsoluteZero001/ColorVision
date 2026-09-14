# ColorVision 1.2

ColorVision 是运行在 Windows 本机的颜色采集与识别系统。V1.2 提供可交付的 onedir EXE，
最终用户不需要安装 Python、Node.js 或 npm。

V1.2 将前端启动与摄像头初始化解耦。即使没有摄像头、摄像头被占用或运行中断开，
FastAPI 与 Vue 页面仍会正常启动，并显示可恢复的 Camera 状态。

完整流程：

```text
双击 ColorVision.exe
  -> 启动本地 FastAPI
  -> 托管 Vue 生产页面
  -> 自动打开默认浏览器
  -> 初始化 CameraService 并检测摄像头
  -> 摄像头实时画面
  -> 拍照与 ROI 框选
  -> RGB / LAB / HEX
  -> Mock 或真实 API 上传
```

## EXE 使用

发布目录：

```text
dist/ColorVision/
├── ColorVision.exe
├── README.md
└── _internal/
```

使用步骤：

1. 保持整个 `ColorVision` 目录完整，不要只复制 EXE。
2. 双击 `ColorVision.exe`。
3. 等待默认浏览器自动打开 `http://127.0.0.1:8000/`。
4. 系统会自动检测并打开第一台可用摄像头；没有设备时可切换到 Mock Camera。
5. 点击“拍照”，在图片上拖动 ROI。
6. 点击“识别颜色”，查看 RGB、LAB 和 HEX。
7. 点击“上传服务器”完成 Mock 或真实 API 上传。
8. 在“设置”页面点击“退出 ColorVision”可正确释放摄像头并关闭服务。

重复双击 EXE 时，程序会检测现有服务并提示 ColorVision 已经在运行。

## 首次运行目录

第一次运行会在 EXE 同级生成：

```text
ColorVision/
├── config/
│   └── config.json
└── data/
    ├── captures/
    ├── results/
    └── logs/
```

默认配置：

```json
{
  "api_url": "http://127.0.0.1:9000/api/color",
  "token": "",
  "camera_id": "CAM-001",
  "auto_upload": false,
  "mock_mode": true,
  "timeout": 10.0,
  "port": 8000
}
```

配置说明：

- `api_url`：真实上传 API 地址。
- `token`：以 `Authorization: Bearer <token>` 发送，可为空。
- `camera_id`：上传数据中的设备标识。
- `auto_upload`：颜色识别完成后自动上传。
- `mock_mode`：`true` 时不访问外部服务器。
- `timeout`：外部 API 超时时间，单位秒。
- `port`：本地服务端口，修改后需要重启 EXE。

也可以使用环境变量指定其他配置文件：

```powershell
$env:COLORVISION_CONFIG = "D:\ColorVisionData\config.json"
```

## Camera 状态与容错

CameraService 支持以下状态：

| 状态 | 含义 | 页面操作 |
| --- | --- | --- |
| `initializing` | 正在检测或初始化 | 等待 |
| `available` | 真实摄像头已打开 | 实时预览、拍照 |
| `not_found` | 未检测到摄像头 | 重新检测、使用 Mock |
| `open_failed` | 摄像头存在但无法打开 | 重新检测、使用 Mock |
| `busy` | 设备可能被其他程序占用 | 重新检测、使用 Mock |
| `disconnected` | 运行中设备断开 | 重新连接、使用 Mock |
| `read_failed` | 当前帧读取失败 | 重新检测、使用 Mock |
| `mock` | Mock Camera 正在运行 | 拍照、切回真实摄像头 |

重新检测和重连会先释放旧 `VideoCapture`，再枚举设备并重新打开，所有生命周期操作会串行执行，
避免快速重复点击造成重复打开或资源泄漏。

设备只有连续读取到尺寸有效且包含可见内容的视频帧后才会进入 `available`；仅
`VideoCapture.isOpened()` 成功不会被判定为可用摄像头。Windows 摄像头驱动在无设备时
可能打开占位视频源并持续返回全黑帧，因此连续全黑或近全黑画面会被视为无效帧。

## Mock Camera 与 Mock Upload

这两项是独立功能：

- Mock Camera：代替摄像头提供动态测试画面，不依赖 USB 摄像头。
- Mock Upload：`mock_mode=true` 时模拟上传服务器响应，不访问外部 API。

当前配置文件中的 `mock_mode` 仍只控制上传行为。Mock Camera 由页面按钮或 Camera API 控制。

## Mock 上传与真实 API

Mock 上传模式：

```json
{
  "mock_mode": true
}
```

页面会显示类似：

```json
{
  "success": true,
  "message": "Mock upload success",
  "request_id": "MOCK-20260914-0001"
}
```

真实 API 模式：

```json
{
  "api_url": "http://your-server/api/color",
  "token": "your-token",
  "mock_mode": false,
  "timeout": 10
}
```

上传使用 `multipart/form-data`，包含：

- `original_image`
- `roi_image`
- `rgb`
- `lab`
- `hex`
- `roi`
- `camera_id`
- `timestamp`

后端会处理超时、HTTP 状态码、无效 JSON 和网络异常。

## 日志

日志位置：

```text
data/logs/colorvision.log
```

日志包含：

- 服务启动与停止
- 摄像头扫描、打开与关闭
- 拍照文件保存
- ROI 颜色分析
- Mock 或真实 API 上传
- 配置迁移与错误
- 未处理异常

EXE 为无控制台窗口模式，正常运行不会持续弹出控制台日志。

## 开发模式

### 安装

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Set-Location .\frontend
npm install
Set-Location ..
```

### 启动

同时启动 FastAPI 和 Vite：

```powershell
.\scripts\dev.ps1
```

也可以使用生产式统一入口：

```powershell
python backend/main.py
```

该入口默认绑定 `127.0.0.1:8000`，不使用 `--reload`，并直接托管
`frontend/dist`。

开发接口文档：

```text
http://127.0.0.1:8000/docs
```

Vite 开发服务器仍可用于前端热更新：

```powershell
Set-Location .\frontend
npm run dev
```

开发服务器地址为 `http://127.0.0.1:5173`。这是唯一仍使用 5173 的场景。

## 自动化测试

运行全部测试、真实摄像头测试和前端生产构建：

```powershell
.\scripts\test.ps1
```

跳过摄像头：

```powershell
.\scripts\test.ps1 -SkipCamera
```

测试覆盖：

- 健康检查、Swagger 和 Vue 托管
- 纯红、纯绿、纯蓝、白色、黑色
- RGB、LAB、HEX 范围与通道顺序
- ROI 零尺寸和越界校验
- 配置默认值、持久化和旧字段迁移
- Mock 上传响应
- 无摄像头、设备占用和运行中断开状态
- Mock Camera 拍照、存储与静态预览
- 真实摄像头拍照、存储与静态预览

## 构建 EXE

```powershell
.\scripts\build.ps1
```

构建流程：

1. 执行 Vue TypeScript 检查和 `npm run build`。
2. 校验 `frontend/dist/index.html` 和 `frontend/dist/assets` 是否完整。
3. 使用 `colorvision.spec` 收集后端、OpenCV、Python 依赖和 Vue 资源。
4. 生成 PyInstaller onedir 目录。
5. 校验发布目录内的 Vue 资源。
6. 将 README 复制到发布目录。

输出：

```text
dist/ColorVision/ColorVision.exe
```

只构建前端：

```powershell
.\scripts\build.ps1 -FrontendOnly
```

项目使用 onedir，不使用 onefile。稳定性优先于单文件体积。

## API 概览

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| GET | `/api/health` | 健康状态 |
| GET、PUT | `/api/config` | 读取或保存配置 |
| GET | `/api/camera/list` | 枚举摄像头 |
| GET | `/api/camera/status` | 摄像头状态 |
| POST | `/api/camera/open` | 打开摄像头 |
| POST | `/api/camera/detect` | 释放旧设备、重新检测并打开 |
| POST | `/api/camera/reconnect` | 重连指定或首台可用摄像头 |
| POST | `/api/camera/mock` | 切换到 Mock Camera |
| POST | `/api/camera/close` | 关闭摄像头 |
| GET | `/api/camera/stream` | MJPEG 实时画面 |
| POST | `/api/camera/capture` | 拍照 |
| POST | `/api/color/analyze` | ROI 颜色分析 |
| POST | `/api/upload` | Mock 或真实上传 |
| POST | `/api/system/shutdown` | 托管模式优雅退出 |

## 摄像头故障排查

1. 关闭 Windows 相机、Teams、Zoom、浏览器会议等可能占用摄像头的程序。
2. 检查 Windows 设置中的“隐私和安全性 -> 相机”权限。
3. 重新插拔 USB 摄像头。
4. 确认没有重复运行的 `ColorVision.exe`。
5. 查看 `data/logs/colorvision.log` 中的摄像头错误。
6. 使用 Windows“相机”应用确认设备本身可以工作。

当前版本只允许一台进程打开一台摄像头。不同时支持多摄像头并发采集。

## 常见错误

`CAMERA_OPEN_FAILED`：

摄像头不存在、驱动不可用，或者已被其他程序占用。

`CAMERA_DEVICE_BUSY`：

摄像头可能正在被其他相机、会议或浏览器程序占用。

`CAMERA_DISCONNECTED`：

摄像头运行过程中断开，重新连接设备后可再次检测。

`CAMERA_READ_FAILED`：

摄像头仍被打开，但当前帧读取失败。

`CAPTURE_FAILED`：

摄像头已连接，但当前帧读取失败。重新打开摄像头或重新插拔设备。

`INVALID_ROI`：

ROI 宽高为 0，或者选区超出原图范围。

`IMAGE_READ_FAILED`：

上传图片为空、格式不支持或超过 25 MB。

`API_TIMEOUT`：

外部 API 在配置的 `timeout` 时间内未响应。

`API_REQUEST_FAILED`：

外部 API 网络失败、返回非 2xx，或返回了无效 JSON。

`端口已被其他程序占用`：

关闭占用端口的程序，或者修改 `config/config.json` 中的 `port` 后重启。

## 已知限制

- 当前为 onedir 版本，必须保留整个发布目录。
- 摄像头枚举不读取厂商友好名称。
- 同一时间只管理一台摄像头。
- 颜色算法尚未进行专业色卡和白平衡校准。
- Token 以明文保存在本机 JSON 配置中。
- 当前未加入 AI 目标检测、分割、跟踪或自动布料识别。
