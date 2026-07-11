# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包設定：把 FastAPI 伺服器 + 前端 dist + 資料打包成單一 Windows exe。

建置： .venv\\Scripts\\pyinstaller.exe jobcopilot.spec --noconfirm
產物： dist\\JobCopilot.exe（單一檔，雙擊啟動、開瀏覽器）。
"""
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

from packaging_support import conda_runtime_binaries

datas = []
binaries = []
hiddenimports = []

# A venv created from conda Python keeps extension modules in the base prefix,
# while their dependent DLLs live in Library/bin. PyInstaller does not detect
# that layout when the venv itself has no conda-meta directory.
binaries += conda_runtime_binaries(sys.base_prefix)

# 唯讀資源：前端建置產物 + demo/fallback 資料（不打包 *.sqlite 等可寫入檔）。
datas += [
    ("frontend/dist", "frontend/dist"),
    ("data/fallback_jobs.json", "data"),
    ("data/demo_profile.json", "data"),
    ("data/demo_jobs", "data/demo_jobs"),
]

# 重依賴：collect_all 一次把套件的 py + 資料檔 + 動態 import 都帶上。
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
    "webview", "pythonnet", "clr_loader",  # 原生視窗（pywebview + WebView2）
]
for _pkg in _COLLECT:
    try:
        d, b, h = collect_all(_pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# 動態載入的子模組：我們自己的 app 套件（uvicorn 以字串 import）、uvicorn driver、checkpoint 後端。
hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += [
    "app.server",
    "langgraph.checkpoint.sqlite",
    "pypdf",
    "tiktoken_ext.openai_public",
    "clr",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
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
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Jobsmith",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)
