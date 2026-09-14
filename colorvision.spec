# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    copy_metadata,
)

PROJECT_ROOT = Path(SPECPATH).resolve()

datas = [
    (
        str(PROJECT_ROOT / "backend" / "config" / "config.json"),
        "backend/config",
    ),
    (
        str(PROJECT_ROOT / "frontend" / "dist"),
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
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="ColorVision",
)
