# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller settings for the unsigned macOS app bundle.

Build on macOS only:
    python -m PyInstaller jobsmith-macos.spec --noconfirm --clean

Output:
    dist/Jobsmith.app
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules
from pathlib import Path

datas = []
binaries = []
hiddenimports = []
icon_path = Path("build/macos/Jobsmith.icns")

datas += [
    ("frontend/dist", "frontend/dist"),
    ("data/fallback_jobs.json", "data"),
    ("data/demo_profile.json", "data"),
    ("data/demo_jobs", "data/demo_jobs"),
]

_COLLECT = [
    "fastapi", "starlette", "uvicorn", "pydantic", "pydantic_core",
    "langchain", "langchain_core", "langchain_text_splitters",
    "langchain_anthropic", "langchain_openai",
    "langgraph", "langgraph_checkpoint", "langgraph_sdk",
    "openai", "anthropic", "tiktoken", "tiktoken_ext",
    "bs4", "soupsieve", "lxml", "docx", "pypdf",
    "dotenv", "httpx", "httpcore", "requests", "certifi",
    "urllib3", "charset_normalizer", "idna", "anyio", "sniffio", "h11",
    "jsonschema", "jsonschema_specifications", "referencing",
    "tenacity", "orjson", "yaml", "regex",
    "aiosqlite", "sqlite_vec",
    "webview", "objc", "Foundation", "AppKit", "WebKit", "Quartz",
    "Security", "UniformTypeIdentifiers",
]
for _pkg in _COLLECT:
    try:
        d, b, h = collect_all(_pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += [
    "app.server",
    "langgraph.checkpoint.sqlite",
    "pypdf",
    "tiktoken_ext.openai_public",
    "webview.platforms.cocoa",
]

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide2", "PySide6",
        "pytest", "IPython", "notebook", "jupyter",
        "pythonnet", "clr_loader", "clr",
        "webview.platforms.edgechromium", "webview.platforms.winforms",
        "webview.platforms.win32", "webview.platforms.mshtml",
        "webview.platforms.gtk", "webview.platforms.qt", "webview.platforms.cef",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Jobsmith",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Jobsmith",
)

app = BUNDLE(
    coll,
    name="Jobsmith.app",
    icon=str(icon_path) if icon_path.exists() else None,
    bundle_identifier="io.github.kevin333353.jobsmith",
    info_plist={
        "CFBundleDisplayName": "Jobsmith",
        "CFBundleName": "Jobsmith",
        "CFBundleShortVersionString": "0.1.1",
        "CFBundleVersion": "0.1.1",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSAppTransportSecurity": {
            "NSAllowsLocalNetworking": True,
            "NSAllowsArbitraryLoadsInWebContent": True,
        },
    },
)
