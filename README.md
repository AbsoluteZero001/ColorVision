# ColorVision

ColorVision 是一个运行在 Windows 本机的机器视觉颜色采集与识别系统。当前仓库已完成
Phase 1：项目分层、配置基础、FastAPI 骨架、Vue 3/Vite 骨架、开发脚本和打包预留入口。

## 当前范围

已建立：

- FastAPI 本地服务与 Swagger `/docs`
- 统一成功/失败响应模型和全局异常处理
- JSON 配置读取、校验与原子写入
- 日志输出到 `data/logs/`
- 摄像头、图像、颜色、上传服务边界
- Vue 3 + TypeScript + Vue Router + Axios 前端骨架
- 工作台、设置页和基础工业软件样式
- PowerShell 开发与构建脚本
- PyInstaller 所需运行时路径设计

尚未实现：

- Phase 3：摄像头枚举与 OpenCV 采集
- Phase 4：拍照与图片持久化
- Phase 5：ROI 颜色算法
- Phase 7：完整页面交互闭环
- Phase 8：外部 API 上传与 Mock 上传
- Phase 10：最终 EXE 配置与产物

当前摄像头、颜色分析和上传接口会明确返回 HTTP `501 FEATURE_NOT_IMPLEMENTED`，不会返回
伪造的识别结果。

## 目录

```text
ColorVision/
├── backend/
│   ├── main.py                 # FastAPI 入口、异常处理、路由注册
│   ├── api/                    # HTTP 路由层
│   ├── services/               # 相机、图像、颜色、上传、配置服务
│   ├── models/                 # Pydantic 数据模型
│   ├── utils/                  # 路径、日志、图像和错误工具
│   └── config/config.json      # 开发环境 JSON 配置
├── frontend/
│   └── src/                    # Vue 3 页面、组件、服务与类型
├── data/
│   ├── captures/               # 拍摄原图
│   ├── results/                # 分析结果与 ROI 图
│   └── logs/                   # 运行日志
├── scripts/
│   ├── dev.ps1
│   └── build.ps1
├── build/                      # PyInstaller 工作目录
├── requirements.txt
└── README.md
```

## 环境要求

- Windows 10/11
- Python 3.11 或更高版本
- Node.js 20.19 或更高版本
- npm 10 或更高版本

## 首次安装

在项目根目录打开 PowerShell：

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

如果 PowerShell 禁止执行本地脚本，可在当前终端临时放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 启动

### 同时启动后端和前端

```powershell
.\scripts\dev.ps1
```

后端运行于 `http://127.0.0.1:8000`，前端运行于 `http://127.0.0.1:5173`。Vite 会将
`/api` 请求代理到 FastAPI。

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

Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

## 配置

开发环境配置位于 `backend/config/config.json`：

```json
{
  "api_url": "http://127.0.0.1:9000/api/color",
  "token": "",
  "camera_id": "CAM-001",
  "auto_upload": false,
  "mock_mode": true
}
```

可以通过前端“设置”页面或 API 修改：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/config" `
  -Method Get
```

`mock_mode=true` 时，后续上传服务将走本地模拟流程，不依赖真实服务器。打包运行时配置会
放在 EXE 同级的 `config/config.json`，不会依赖开发机绝对路径。

也可以通过环境变量覆盖配置文件位置：

```powershell
$env:COLORVISION_CONFIG = "D:\ColorVisionData\config.json"
```

## API 概览

| 方法 | 路径 | Phase 1 状态 |
| --- | --- | --- |
| GET | `/api/health` | 可用 |
| GET | `/api/config` | 可用 |
| PUT | `/api/config` | 可用 |
| GET | `/api/camera/list` | 已定义路由，返回 501 |
| GET | `/api/camera/status` | 已定义路由，返回 501 |
| POST | `/api/camera/open` | 已定义路由，返回 501 |
| POST | `/api/camera/close` | 已定义路由，返回 501 |
| POST | `/api/camera/capture` | 已定义路由，返回 501 |
| POST | `/api/color/analyze` | 已定义路由，返回 501 |
| POST | `/api/upload` | 已定义路由，返回 501 |

成功响应统一为：

```json
{
  "success": true,
  "data": {}
}
```

失败响应统一为：

```json
{
  "success": false,
  "message": "Camera not available",
  "code": "CAMERA_NOT_AVAILABLE"
}
```

## 当前验证方法

检查后端和配置：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/config"
```

检查前端类型与生产构建：

```powershell
Set-Location .\frontend
npm run typecheck
npm run build
Set-Location ..
```

摄像头、颜色识别和 Mock 上传的测试命令会在对应 Phase 完成并验证后补充。

## 前端构建

```powershell
.\scripts\build.ps1 -FrontendOnly
```

构建输出位于 `frontend/dist/`。

## EXE 预留

最终 EXE 的启动顺序为：

1. 动态解析运行时目录并初始化 `config/config.json`
2. 启动 FastAPI/Uvicorn 本地服务
3. 提供或加载构建后的 Vue 前端
4. 打开本机浏览器或内置窗口
5. 用户开始采集

`scripts/build.ps1` 已预留 PyInstaller 调用，但 `colorvision.spec` 将在 Phase 10 创建。

## 后续扩展边界

自动目标检测、颜色识别、目标跟踪等能力应新增独立服务并接入现有 `CameraService`、
`ImageService`、`ColorService` 边界。当前阶段不引入数据库、Redis、登录、权限、Docker、
MySQL 或 Spring Boot。
