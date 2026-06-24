"""歷史投遞包：完成的投遞包自動存 sqlite，可回查/重開/刪除。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.store import db

_PKG_KEYS = ("parsed_job", "match_report", "company_brief",
             "tailored_resume", "cover_letter", "interview_kit", "critique")


def save_package(final_state: dict, thread_id: str | None = None) -> int:
    """存一筆投遞包；傳入 thread_id 時具冪等性：同一 thread 已存過則不重存（回原 id）。

    避免使用者重送 /api/resume（雙擊核可、SSE 斷線重連、網路重試）在已完成的 thread 上
    重複 INSERT 同一份投遞包，造成歷史清單出現重複項。
    """
    pj = final_state.get("parsed_job") or {}
    mr = final_state.get("match_report") or {}
    package = {k: final_state.get(k) for k in _PKG_KEYS}
    profile = final_state.get("profile")
    conn = db.get_conn()
    with db.LOCK:
        if thread_id:
            dup = conn.execute(
                "SELECT id FROM packages WHERE thread_id=?", (thread_id,)).fetchone()
            if dup:
                return int(dup["id"])
        cur = conn.execute(
            "INSERT INTO packages(created_at,job_title,company,match_score,jd_text,"
            "profile_json,package_json,approved,thread_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(),
             pj.get("title") or "（未命名）", pj.get("company") or "",
             int(mr.get("score") or 0), final_state.get("jd_text") or "",
             json.dumps(profile, ensure_ascii=False) if profile else None,
             json.dumps(package, ensure_ascii=False),
             1 if final_state.get("approved") else 0,
             thread_id))
        conn.commit()
        return int(cur.lastrowid)


def list_packages() -> list[dict]:
    conn = db.get_conn()
    # 讀取也納入 LOCK：共用單一 Connection 在 threadpool 多執行緒下並非執行緒安全，
    # 與終局自動存檔同時發生時可能拋 ProgrammingError。
    with db.LOCK:
        rows = conn.execute(
            "SELECT id,created_at,job_title,company,match_score,approved "
            "FROM packages ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_package(pid: int) -> dict | None:
    conn = db.get_conn()
    with db.LOCK:
        r = conn.execute("SELECT * FROM packages WHERE id=?", (pid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["package"] = json.loads(d.pop("package_json") or "{}")
    d["profile"] = json.loads(d["profile_json"]) if d.get("profile_json") else None
    d.pop("profile_json", None)
    return d


def delete_package(pid: int) -> None:
    conn = db.get_conn()
    with db.LOCK:
        conn.execute("DELETE FROM packages WHERE id=?", (pid,))
        conn.commit()
