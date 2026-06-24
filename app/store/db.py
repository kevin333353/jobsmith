"""應用層 sqlite（與 LangGraph checkpoints 分開）：歷史投遞包 + 使用者記憶。

單一共用連線（check_same_thread=False 供 FastAPI threadpool 共用）；寫入用 LOCK 串行化。
路徑由 COPILOT_APP_DB 決定，預設 data/app.sqlite；測試用 :memory:（單例連線共用同一 in-memory DB）。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
LOCK = threading.Lock()
_conn: sqlite3.Connection | None = None


def _db_path() -> str:
    return os.environ.get("COPILOT_APP_DB", str(_ROOT / "data" / "app.sqlite"))


def _init(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS packages("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, job_title TEXT, company TEXT, "
        "match_score INTEGER, jd_text TEXT, profile_json TEXT, package_json TEXT, approved INTEGER, "
        "thread_id TEXT)")
    # 既有資料庫（M11 前建立）缺 thread_id 欄位時補上——冪等存檔用。
    cols = {r[1] for r in conn.execute("PRAGMA table_info(packages)").fetchall()}
    if "thread_id" not in cols:
        conn.execute("ALTER TABLE packages ADD COLUMN thread_id TEXT")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_memory("
        "id INTEGER PRIMARY KEY CHECK (id=1), profile_json TEXT, preferences_json TEXT, updated_at TEXT)")
    conn.commit()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_db_path(), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init(_conn)
    return _conn


def init_db() -> None:
    get_conn()
