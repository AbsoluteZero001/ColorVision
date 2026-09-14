# ColorVision 1.1

ColorVision 是运行在 Windows 本机的颜色采集与识别系统。V1.1 提供可交付的 onedir EXE，
最终用户不需要安装 Python、Node.js 或 npm。

完整流程：

```text
双击 ColorVision.exe
  -> 启动本地 FastAPI
  -> 托管 Vue 生产页面
  -> 自动打开默认浏览器
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
4. 系统会自动检测并打开第一台可用摄像头。
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

## Mock 与真实 API

Mock 模式：

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
- 真实摄像头拍照、存储与静态预览

## 构建 EXE

```powershell
.\scripts\build.ps1
```

构建流程：

1. 执行 Vue TypeScript 检查和 `npm run build`。
2. 使用 `colorvision.spec` 收集后端、OpenCV、Python 依赖和 Vue 资源。
3. 生成 PyInstaller onedir 目录。
4. 将 README 复制到发布目录。

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
