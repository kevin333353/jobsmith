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


def create_running_package(thread_id: str, jd_text: str, title: str,
                           profile: dict | None = None) -> int:
    """背景產生投遞包：先建一筆『進行中(running)』佔位，跑完再用 update_package_result 補成品。

    使用者一按「產生投遞包」就有紀錄、可離開頁面；pipeline 在伺服器背景續跑。
    """
    conn = db.get_conn()
    with db.LOCK:
        cur = conn.execute(
            "INSERT INTO packages(created_at,job_title,company,match_score,jd_text,"
            "profile_json,package_json,approved,thread_id,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), title or "（產生中）", "",
             0, jd_text or "",
             json.dumps(profile, ensure_ascii=False) if profile else None,
             None, 0, thread_id, "running"))
        conn.commit()
        return int(cur.lastrowid)


def update_package_result(pid: int, final_state: dict) -> None:
    """背景流程完成：補上成品並標記 status='done'（approved 維持 0＝待審，由使用者到我的投遞包核可）。"""
    pj = final_state.get("parsed_job") or {}
    mr = final_state.get("match_report") or {}
    package = {k: final_state.get(k) for k in _PKG_KEYS}
    conn = db.get_conn()
    with db.LOCK:
        conn.execute(
            "UPDATE packages SET job_title=?, company=?, match_score=?, package_json=?, "
            "status='done' WHERE id=?",
            (pj.get("title") or "（未命名）", pj.get("company") or "",
             int(mr.get("score") or 0),
             json.dumps(package, ensure_ascii=False), pid))
        conn.commit()


def set_status(pid: int, status: str) -> None:
    """更新生命週期狀態（running / done / failed）。"""
    conn = db.get_conn()
    with db.LOCK:
        conn.execute("UPDATE packages SET status=? WHERE id=?", (status, pid))
        conn.commit()


def mark_stale_running_failed() -> int:
    """伺服器啟動時把殘留的 running 收尾為 failed（背景執行緒不跨程序重啟存活，否則會永遠卡進行中）。"""
    conn = db.get_conn()
    with db.LOCK:
        cur = conn.execute("UPDATE packages SET status='failed' WHERE status='running'")
        conn.commit()
        return cur.rowcount


def list_packages() -> list[dict]:
    conn = db.get_conn()
    # 讀取也納入 LOCK：共用單一 Connection 在 threadpool 多執行緒下並非執行緒安全，
    # 與終局自動存檔同時發生時可能拋 ProgrammingError。
    with db.LOCK:
        rows = conn.execute(
            "SELECT id,created_at,job_title,company,match_score,approved,status "
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


def set_approved(pid: int, approved: bool) -> None:
    """更新某投遞包的核可狀態（「我的投遞包」的核可動作；批次產生的待審包在此核可）。"""
    conn = db.get_conn()
    with db.LOCK:
        conn.execute("UPDATE packages SET approved=? WHERE id=?",
                     (1 if approved else 0, pid))
        conn.commit()


def delete_package(pid: int) -> None:
    conn = db.get_conn()
    with db.LOCK:
        conn.execute("DELETE FROM packages WHERE id=?", (pid,))
        conn.commit()
