# 颜色识别系统（ColorVision）V1.5.0

颜色识别系统是运行在 Windows 本机的颜色采集与识别系统。应用采用统一父目录架构与 Windows 标准安装程序（`ColorVision_Setup.exe`）交付，所有程序主体、运行依赖、配置、图片、上传历史、本地数据库、缓存和运行日志均集中存放在同一个安装父目录中，不向 `AppData` 或系统分散目录写入业务数据，普通用户无需管理员权限即可日常启动和使用。

完整流程：

```text
双击桌面快捷方式 ColorVision
  -> 启动安装目录中的 ColorVision.exe（加载 _internal 依赖）
  -> 启动本地 FastAPI 并托管 Vue 生产页面
  -> 自动打开默认浏览器
  -> 检测浏览器或 Mock 摄像头
  -> 摄像头实时画面
  -> 拍照与 ROI 框选
  -> RGB / LAB / HEX
  -> Mock 或真实 API 上传
```

## 安装与目录结构

运行安装程序 `ColorVision_Setup.exe`：

1. 默认安装路径为 `D:\ColorVision`（若本机不存在可用 D 盘，安装向导会自动提示并切换至其他可用磁盘；支持自定义任意有效子目录）。
2. 安装过程中会合理设置 `config`、`data`、`cache` 和 `logs` 的普通用户写入（Modify）权限，不赋予整块磁盘完全控制权限。
3. 安装完成后会自动在桌面创建 `ColorVision.lnk` 快捷方式（指向 `<安装目录>\ColorVision.exe` 并配置正确工作目录与图标），并在开始菜单创建启动与卸载入口。
4. 双击桌面快捷方式即可由普通用户直接启动，无需每次以管理员身份运行。

安装完成后，所有文件统一集中在同一个父目录下：

```text
D:\ColorVision\
│
├── ColorVision.exe              # 主程序入口
│
├── _internal\                   # PyInstaller 运行依赖、DLL 与前端资源
│
├── config\                      # 统一配置目录
│   ├── app.json                 # 安装路径、端口、留存策略与日志配置
│   ├── api-config.json          # 上传 API URL、Token、超时与 Mock 模式配置
│   └── camera.json              # 摄像头标识等设备配置
│
├── data\                        # 业务数据目录
│   ├── photos\
│   │   ├── captures\            # 拍照保存的本地图片
│   │   └── uploads\             # 上传日志关联的原图与识别区域图
│   ├── history\                 # 上传历史 JSON 快照记录
│   └── database\
│       └── colorvision.db       # SQLite 本地数据库
│
├── cache\                       # 统一运行时缓存目录
│
├── logs\                        # 统一运行日志目录（colorvision.log）
│
└── README.md                    # 使用说明
```

> 说明：程序内部通过 `backend/utils/paths.py` 动态识别当前安装根目录（不写死 `D:\ColorVision`，也不受工作目录变化影响）。无论安装到 `D:\ColorVision` 还是 `E:\Software\ColorVision`，所有子目录均根据实际安装路径动态定位。

## 升级与卸载

- **覆盖升级**：直接运行新版本 `ColorVision_Setup.exe` 到原安装目录，仅更新 `ColorVision.exe`、`_internal\` 和 `README.md`，自动保留已有 `config\`、`data\`（含历史图片、上传历史和数据库）及 `logs\`。旧版 `config/config.json` 与 `data/logs/colorvision.db` 在首次启动时也会自动迁移至新目录结构。
- **程序卸载**：卸载默认仅删除程序主体与快捷方式，**自动保留 `config\`、`data\`、历史图片与本地数据库**；卸载完成时会提供可选项确认是否清理整个 ColorVision 文件夹，并在选择完全清理前给出明确的数据删除警告。

## 使用步骤

1. 双击桌面快捷方式 `ColorVision`。
2. 等待默认浏览器自动打开 `http://127.0.0.1:8000/`。
3. 系统会自动请求并打开可用摄像头；没有设备时可切换到 Mock Camera。
4. 点击“拍照”，在图片上拖动 ROI。
5. 点击“识别颜色”，查看 RGB、LAB 和 HEX。
6. 点击“上传服务器”完成 Mock 或真实 API 上传。
7. 在“日志”页面查看北京时间、上传图片、ROI 图片和颜色参数。
8. 在“设置”页面修改并持久化 API 与设备参数，或点击“退出颜色识别系统”优雅释放资源并关闭服务。

## 配置说明

配置文件统一存放在 `<安装目录>\config\`：

1. **`config/app.json`**
   - `app_name` / `version` / `install_dir`：应用标识与实际安装根目录。
   - `port`：本地服务端口（默认 `8000`，修改后需重启）。
   - `image_retention_days` / `max_image_count`：拍照图片留存策略（`0` 表示不自动清理）。
   - `log_enabled` / `log_image_storage_enabled` / `log_retention_days` / `max_log_count`：上传日志与留存策略。
2. **`config/api-config.json`**
   - `api_url`：真实上传 API 地址。
   - `token`：以 `Authorization: Bearer <token>` 发送，可为空。
   - `auto_upload`：颜色识别完成后自动上传。
   - `mock_mode`：`true` 时使用本地模拟上传，不访问外部服务器。
   - `timeout`：外部 API 超时时间（秒）。
3. **`config/camera.json`**
   - `camera_id`：上传数据中的摄像头设备标识。

也可以使用环境变量指定自定义根目录或覆盖配置文件：

```powershell
$env:COLORVISION_ROOT = "E:\Software\ColorVision"
$env:COLORVISION_CONFIG = "E:\Custom\config.json"
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

## 上传日志与运行日志

- 上传记录索引：`data/database/colorvision.db`
- 上传历史快照：`data/history/upload_*.json`
- 拍照与上传图片：`data/photos/captures/`、`data/photos/uploads/`
- 运行日志：`logs/colorvision.log`
- 运行时缓存：`cache/`

应用不会自动向 `AppData` 写入配置或业务数据，也不会将图片保存到安装根目录。

## 开发模式

### 安装依赖

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Set-Location .\frontend
npm install
Set-Location ..
```

### 启动开发服务

```powershell
.\scripts\dev.ps1
```

或使用统一后端入口（托管 `frontend/dist`）：

```powershell
python backend/main.py
```

## 自动化测试

```powershell
.\scripts\test.ps1 -SkipCamera
```

## 构建与打包（`ColorVision.exe` 与 `ColorVision_Setup.exe`）

```powershell
.\scripts\build.ps1
```

构建流程：

1. 编译并校验前端 Vue 生产构建（`frontend/dist`）。
2. 使用 `colorvision.spec`（PyInstaller `onedir` 模式）打包出 `ColorVision.exe` 与 `_internal\` 依赖目录，并内嵌 `assets/ColorVision.ico` 图标与版本信息。
3. 生成干净的统一目录结构到 `dist/ColorVision/`。
4. 调用 Inno Setup 6（`ISCC.exe`）编译 `installer/ColorVision.iss`，生成最终安装程序 `dist/ColorVision_Setup.exe`。

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
| GET | `/api/logs` | 分页读取本地上传日志 |
| DELETE | `/api/logs/{id}` | 删除单条日志及其图片与历史 |
| DELETE | `/api/logs` | 清空全部日志、图片与历史 |
| POST | `/api/system/shutdown` | 托管模式优雅退出 |

## Code signing policy

Free code signing provided by SignPath.io, certificate by SignPath Foundation.

### Team roles

- Committers and reviewers: AbsoluteZero
- Approvers: AbsoluteZero

### Privacy policy

[ColorVision Privacy Policy](https://github.com/AbsoluteZero001/ColorVision/blob/main/PRIVACY.md)

## License

本项目采用 [MIT License](https://github.com/AbsoluteZero001/ColorVision/blob/main/LICENSE)。
