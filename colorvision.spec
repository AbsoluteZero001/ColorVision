# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    copy_metadata,
)
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

PROJECT_ROOT = Path(SPECPATH).resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import __version__


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in version.split(".")]
    return tuple((parts + [0, 0, 0, 0])[:4])


APP_VERSION = _version_tuple(__version__)
VERSION_INFO = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=APP_VERSION,
        prodvers=APP_VERSION,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "ColorVision"),
                        StringStruct(
                            "FileDescription",
                            "ColorVision Color Recognition System",
                        ),
                        StringStruct("FileVersion", __version__),
                        StringStruct("ProductName", "ColorVision"),
                        StringStruct("ProductVersion", __version__),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

if not FRONTEND_INDEX.is_file():
    raise SystemExit(
        f"Vue production entry is missing: {FRONTEND_INDEX}. "
        "Run the frontend build before packaging."
    )

if not FRONTEND_ASSETS.is_dir() or not any(FRONTEND_ASSETS.iterdir()):
    raise SystemExit(
        f"Vue production assets are missing or empty: {FRONTEND_ASSETS}. "
        "Run the frontend build before packaging."
    )

datas = [
    (
        str(PROJECT_ROOT / "backend" / "config" / "config.json"),
        "backend/config",
    ),
    (
        str(FRONTEND_DIST),
        "frontend/dist",
    ),
]
binaries = []
hiddenimports = collect_submodules("backend")

for package_name in (
    "cv2",
    "fastapi",
    "httpx",
    "httpcore",
    "multipart",
    "pydantic",
    "starlette",
    "uvicorn",
    "certifi",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(
        package_name
    )
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
]

for distribution_name in (
    "fastapi",
    "httpcore",
    "httpx",
    "numpy",
    "opencv-python",
    "Pillow",
    "pydantic",
    "python-multipart",
    "starlette",
    "uvicorn",
):
    try:
        datas += copy_metadata(distribution_name)
    except Exception:
        pass

analysis = Analysis(
    [str(PROJECT_ROOT / "backend" / "launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ColorVision",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=VERSION_INFO,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="ColorVision",
)
