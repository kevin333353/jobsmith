"""使用者記憶：跨 session 記住最近履歷與個人化偏好（user_memory 單列）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.store import db


def get_memory() -> dict:
    conn = db.get_conn()
    # 讀取也納入 LOCK（共用單一 Connection 非執行緒安全，見 history.list_packages 註解）。
    with db.LOCK:
        r = conn.execute(
            "SELECT profile_json, preferences_json FROM user_memory WHERE id=1").fetchone()
    if not r:
        return {"profile": None, "preferences": {}}
    return {
        "profile": json.loads(r["profile_json"]) if r["profile_json"] else None,
        "preferences": json.loads(r["preferences_json"]) if r["preferences_json"] else {},
    }


def _upsert(*, profile_json: str | None = None, preferences_json: str | None = None) -> None:
    conn = db.get_conn()
    with db.LOCK:
        cur = conn.execute("SELECT profile_json, preferences_json FROM user_memory WHERE id=1").fetchone()
        now = datetime.now(timezone.utc).isoformat()
        if cur is None:
            conn.execute(
                "INSERT INTO user_memory(id, profile_json, preferences_json, updated_at) VALUES(1,?,?,?)",
                (profile_json, preferences_json, now))
        else:
            pj = profile_json if profile_json is not None else cur["profile_json"]
            prefs = preferences_json if preferences_json is not None else cur["preferences_json"]
            conn.execute(
                "UPDATE user_memory SET profile_json=?, preferences_json=?, updated_at=? WHERE id=1",
                (pj, prefs, now))
        conn.commit()


def save_profile(profile: dict) -> None:
    _upsert(profile_json=json.dumps(profile, ensure_ascii=False))


def save_preferences(prefs: dict) -> None:
    _upsert(preferences_json=json.dumps(prefs, ensure_ascii=False))
