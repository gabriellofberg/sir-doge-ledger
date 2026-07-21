# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SirDoge Ledger desktop bundle."""

from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "sample_data"), "sample_data"),
]

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "app.main",
    "app.config",
    "app.db",
    "app.routers.money",
    "app.routers.life",
    "app.routers.data",
    "app.routers.settings",
    "app.services.auth",
    "app.services.budgets",
    "app.services.categorize",
    "app.services.categories",
    "app.services.data_management",
    "app.services.demo",
    "app.services.import_parse",
    "app.services.import_sessions",
    "app.services.insights",
    "app.services.life",
    "app.services.money",
    "app.services.normalize",
    "app.services.recommendations",
    "app.services.recurring",
    "app.services.security_paths",
    "app.services.settings",
    "openpyxl",
    "bcrypt",
    "multipart",
    "python_multipart",
]

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SirDogeLedger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SirDogeLedger",
)
