# ColorVision

ColorVision 是运行在 Windows 本机的颜色采集与识别软件。V1 MVP 已实现完整业务闭环：

```text
摄像头 -> MJPEG 实时画面 -> 拍照 -> ROI 框选
      -> RGB/LAB/HEX -> 前端显示 -> Mock/真实 API 上传
```

## 已实现功能

- OpenCV 枚举、打开、关闭和读取本机摄像头
- FastAPI 提供浏览器可播放的 MJPEG 实时画面
- 从当前摄像头拍照并保存到 `data/captures/`
- 通过 `/media` 静态地址预览已拍摄图片
- 在拍摄原图上拖动绘制 ROI
- 将浏览器显示坐标按比例换算成原图像素坐标
- ROI 像素中位数统计，并排除少量过暗和过亮像素
- 输出 RGB、标准 CIELAB 和 `#RRGGBB`
- 复制 HEX、重新拍摄和错误提示
- Mock 上传模式，不依赖外部服务器
- 真实 API multipart 上传，支持 Token、超时和错误映射
- JSON 配置读取、修改和持久化
- 文件日志与统一 API 错误响应

## 环境要求

- Windows 10/11
- Python 3.11 或更高版本
- Node.js 20.19 或更高版本
- npm 10 或更高版本

## 安装

项目根目录执行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

安装前端依赖：

```powershell
Set-Location .\frontend
npm install
Set-Location ..
```

如果 PowerShell 禁止执行本地脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 启动

### 一键启动

```powershell
.\scripts\dev.ps1
```

后端地址：`http://127.0.0.1:8000`

前端地址：`http://127.0.0.1:5173`

Swagger：`http://127.0.0.1:8000/docs`

### 分别启动

后端：

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```powershell
Set-Location .\frontend
npm run dev
```

## 页面操作

1. 打开前端后，系统会自动探测并打开第一台可用摄像头。
2. 实时画面显示后点击“拍照”。
3. 在右侧或下方冻结的拍摄图片上按住鼠标左键拖动。
4. 调整到目标区域后点击“识别颜色”。
5. 查看颜色预览、RGB、LAB 和 HEX。
6. 点击“上传服务器”，或先在设置中启用“自动上传”。
7. Mock 模式会在页面显示上传成功和 `request_id`。

浏览器不会直接访问 OpenCV 摄像头对象。所有实时画面由后端编码为 JPEG，再通过
`GET /api/camera/stream` 作为 MJPEG 响应提供给 `<img>`。

## 配置

配置文件：`backend/config/config.json`

```json
{
  "api_url": "http://127.0.0.1:9000/api/color",
  "token": "",
  "camera_id": "CAM-001",
  "auto_upload": false,
  "mock_mode": true,
  "request_timeout_seconds": 10.0
}
```

设置页可以修改以上参数。也可以调用配置 API：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config" -Method Get

$body = @{
    api_url = "http://127.0.0.1:9000/api/color"
    token = ""
    camera_id = "CAM-001"
    auto_upload = $false
    mock_mode = $true
    request_timeout_seconds = 10
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/api/config" `
    -Method Put `
    -ContentType "application/json" `
    -Body $body
```

`mock_mode=true` 时上传在本地完成。将其关闭后，后端会向 `api_url` 发送真实 multipart
请求，并在配置了 Token 时添加 `Authorization: Bearer <token>`。

打包运行后，可编辑配置会放在 EXE 同级的 `config/config.json`。也可用环境变量覆盖位置：

```powershell
$env:COLORVISION_CONFIG = "D:\ColorVisionData\config.json"
```

## 上传字段

`POST /api/upload` 接收：

- `original_image`：原始拍摄图片
- `roi_image`：前端裁剪后的 ROI 图片
- `rgb`：JSON 对象
- `lab`：JSON 对象
- `hex`：`#RRGGBB`
- `roi`：`x/y/width/height` JSON 对象
- `camera_id`：设备标识
- `timestamp`：拍摄时间

Mock 成功响应示例：

```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "Mock upload success",
    "request_id": "MOCK-20260914-0001",
    "mode": "mock"
  }
}
```

## API 概览

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| GET | `/api/health` | 服务健康状态 |
| GET | `/api/config` | 读取本地配置 |
| PUT | `/api/config` | 修改本地配置 |
| GET | `/api/camera/list` | 枚举摄像头 |
| GET | `/api/camera/status` | 查询摄像头状态 |
| POST | `/api/camera/open` | 打开指定摄像头 |
| POST | `/api/camera/close` | 关闭摄像头 |
| GET | `/api/camera/stream` | MJPEG 实时画面 |
| POST | `/api/camera/capture` | 拍照并保存 |
| POST | `/api/color/analyze` | ROI 颜色分析 |
| POST | `/api/upload` | Mock 或真实 API 上传 |

成功响应统一使用：

```json
{
  "success": true,
  "data": {}
}
```

失败响应统一使用：

```json
{
  "success": false,
  "message": "Camera is not open",
  "code": "CAMERA_CLOSED"
}
```

## 颜色计算

`ColorService` 接收 OpenCV BGR 图像：

1. 将 BGR 正确转换为 RGB。
2. 计算 ROI 内像素亮度。
3. 在有效像素比例足够时排除过暗与过亮像素。
4. 对剩余像素按通道取中位数，避免单个坏点影响结果。
5. 使用 OpenCV 标准转换计算 LAB。
6. 将 8-bit OpenCV LAB 规范化：
   - `L = 原始 L * 100 / 255`
   - `a = 原始 a - 128`
   - `b = 原始 b - 128`
7. 生成大写 `#RRGGBB`。

## 构建

前端类型检查与生产构建：

```powershell
.\scripts\build.ps1 -FrontendOnly
```

构建输出位于 `frontend/dist/`。

PyInstaller 打包尚未完成。`scripts/build.ps1` 已预留调用入口，后续需要增加
`colorvision.spec`、前端静态资源收集和 EXE 启动逻辑。

## 已知限制

- 当前进程同一时间只维护一台已打开摄像头。
- 摄像头枚举使用有限索引扫描，不读取 Windows 设备友好名称。
- MJPEG 默认约 15 FPS，网络较慢时可能略低。
- 颜色算法使用鲁棒中位数，不包含光照校正、白平衡或色彩校准。
- 真实外部 API 的字段兼容性由接收服务决定。
- Token 保存在本机 JSON 文件中，尚未接入 Windows 凭据管理器。
- 当前尚未生成最终 EXE。

## 后续建议

1. 增加自动化测试套件和 CI。
2. 增加相机分辨率、曝光和白平衡控制。
3. 增加色彩标定卡和校准流程。
4. 增加 ROI 区域的局部放大与多区域比较。
5. 在 V1 稳定后，再接入目标检测、自动分割或跟踪服务。
