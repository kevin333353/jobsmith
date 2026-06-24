"""搜尋紀錄：把每次職缺搜尋結果（AI 推薦＋指定公司＋技能缺口）存起來，可回看/重開/刪除。

與「投遞包歷史」(history.py) 分開：這裡存的是『搜尋結果整包』，方便依履歷管理、
不會因為 LLM 評分每次不同或即時來源變動而「重找就不見」。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.store import db


def save_search(label: str, profile: dict | None, payload: dict) -> int:
    ai = payload.get("jobs") or []
    company = payload.get("companyJobs") or []
    conn = db.get_conn()
    with db.LOCK:
        cur = conn.execute(
            "INSERT INTO searches(created_at,label,ai_count,company_count,profile_json,payload_json)"
            " VALUES(?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(),
             (label or "未命名搜尋")[:200], len(ai), len(company),
             json.dumps(profile, ensure_ascii=False) if profile else None,
             json.dumps(payload, ensure_ascii=False)))
        conn.commit()
        return int(cur.lastrowid)


def list_searches() -> list[dict]:
    conn = db.get_conn()
    with db.LOCK:
        rows = conn.execute(
            "SELECT id,created_at,label,ai_count,company_count "
            "FROM searches ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_search(sid: int) -> dict | None:
    conn = db.get_conn()
    with db.LOCK:
        r = conn.execute("SELECT * FROM searches WHERE id=?", (sid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["payload"] = json.loads(d.pop("payload_json") or "{}")
    d["profile"] = json.loads(d["profile_json"]) if d.get("profile_json") else None
    d.pop("profile_json", None)
    return d


def delete_search(sid: int) -> None:
    conn = db.get_conn()
    with db.LOCK:
        conn.execute("DELETE FROM searches WHERE id=?", (sid,))
        conn.commit()
