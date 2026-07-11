"""Yourator：v4 jobs JSON API；TLS 驗證失敗時安全降級為 blocked。"""
from __future__ import annotations

from urllib.parse import quote

from app.models import JobPosting, SearchResult
from app.sources.base import http_get

NAME = "yourator"
SEARCHABLE = True
_API = "https://www.yourator.co/api/v4/jobs?term[]={kw}&page={page}"


def search(keywords: str, limit: int = 15, pages: int = 1,
           area: list[str] | None = None) -> SearchResult:
    """搜尋 Yourator；pages>1 時逐頁抓取（API 吃 page 參數）並跨頁去重。

    area：保留參數，本來源不支援來源端地區篩選（地區由結果端 location 過濾處理）。
    """
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    for page in range(1, max(1, pages) + 1):
        try:
            r = http_get(_API.format(kw=quote(keywords), page=page))
            if not r.ok:
                if page == 1:
                    return SearchResult(source=NAME, blocked=True, error=f"HTTP {r.status_code}")
                break
            data = (r.json().get("payload") or {}).get("jobs") or []
        except Exception as e:
            if page == 1:
                return SearchResult(source=NAME, blocked=True, error=str(e)[:150])
            break
        if not data:
            break
        for d in data[:limit]:
            comp = d.get("company") or {}
            tags = d.get("tags") or []
            path = d.get("path") or ""
            url = "https://www.yourator.co" + path if path else ""
            key = url or (d.get("name", "") + (comp.get("brand") or ""))
            if key in seen:
                continue
            seen.add(key)
            jobs.append(JobPosting(
                source=NAME,
                title=d.get("name", ""),
                company=comp.get("brand") or comp.get("enName") or "",
                location=d.get("location"),
                salary=d.get("salary"),
                url=url,
                snippet="、".join(tags) if tags else None,
                requirements=tags,
            ))
    return SearchResult(source=NAME, jobs=jobs)
