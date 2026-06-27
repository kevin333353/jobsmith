"""桌面 App 啟動器：背景跑 FastAPI server，並用系統 WebView 開一個原生視窗。

雙擊即開、不必開終端機或另開瀏覽器；仍是在本機執行、用使用者自己的 Claude Code /
Codex CLI 訂閱（與 run.bat 相同的後端，差別只在改用原生視窗呈現）。

用法：desktop.bat（或 .venv\\Scripts\\python.exe desktop.py）。
需求：先建置前端（cd frontend && npm run build）；Windows 需有 WebView2 執行階段（Win11 內建）。
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import uvicorn
import webview

_TITLE = "Jobsmith"


def _resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).parent


_ROOT = _resource_root()


def _frozen_paths() -> tuple[Path, Path]:
    if sys.platform == "darwin":
        data_dir = Path.home() / "Library" / "Application Support" / "Jobsmith"
        return data_dir, data_dir / ".env"
    exe_dir = Path(sys.executable).parent
    return exe_dir / "JobsmithData", exe_dir / ".env"


def _setup_frozen() -> None:
    """凍結成 exe 時，把可寫入檔案（SQLite、.env）導向 exe 旁的位置，並載入 exe 旁的 .env。

    打包內部是唯讀的，Windows 將資料放 exe 旁邊；macOS 則放 Application Support。
    """
    if not getattr(sys, "frozen", False):
        return
    data_dir, env_file = _frozen_paths()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        data_dir = Path(sys.executable).parent
        env_file = data_dir / ".env"
    os.environ.setdefault("COPILOT_DB", str(data_dir / "checkpoints.sqlite"))
    os.environ.setdefault("COPILOT_APP_DB", str(data_dir / "app.sqlite"))
    os.environ.setdefault("COPILOT_ENV_FILE", str(env_file))
    try:
        from dotenv import load_dotenv
        if env_file.exists():
            load_dotenv(env_file)
    except Exception:
        pass


def _pick_port(preferred: int = 8000) -> int:
    """優先用 8000；若被佔用（例如同時開了 run.bat）就找一個空閒埠，避免衝突。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
        s2.bind(("127.0.0.1", 0))
        return s2.getsockname()[1]


def _wait_until_up(url: str, server: uvicorn.Server, timeout: float = 30.0) -> bool:
    """等 server 起來（poll 首頁）；server 啟動失敗就提早返回 False。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if getattr(server, "started", False):
            try:
                with urlopen(url, timeout=1):
                    return True
            except Exception:
                pass
        time.sleep(0.2)
    return False


def main() -> int:
    _setup_frozen()
    dist_index = _ROOT / "frontend" / "dist" / "index.html"
    if not dist_index.exists():
        print("找不到前端建置產物（frontend/dist）。請先執行：")
        print("    cd frontend && npm run build")
        return 1

    port = _pick_port(8000)
    base = f"http://127.0.0.1:{port}"

    config = uvicorn.Config("app.server:app", host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_until_up(base, server):
        print("伺服器啟動逾時，請改用 run.bat 觀察錯誤訊息。")
        server.should_exit = True
        return 1

    # 開原生視窗；webview.start() 會阻塞直到視窗關閉。
    webview.create_window(_TITLE, base, width=1280, height=860, min_size=(960, 640))
    webview.start()

    # 視窗關閉 → 通知 server 收工。
    server.should_exit = True
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # 視窗模式（無主控台）下，把例外寫到 exe 旁的 log 供回報
        import traceback
        try:
            base = Path(sys.executable).parent if getattr(sys, "frozen", False) else _ROOT
            log = base / "JobsmithData"
            log.mkdir(exist_ok=True)
            (log / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise
