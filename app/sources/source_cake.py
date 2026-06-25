"""Cake（cake.me）：解析搜尋頁 __NEXT_DATA__ 的 initialState.jobSearch.entityByPathId。

Cake 已改用 Algolia client-side 搜尋，但 SSR 仍把首頁結果放進 __NEXT_DATA__ 的
initialState.jobSearch.entityByPathId（slug -> 職缺）。本機憑證鏈問題用 verify=False；失敗即降級。
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from app.models import JobPosting, SearchResult
from app.sources.base import clean, http_get

NAME = "cake"
SEARCHABLE = True
_PAGE = "https://www.cake.me/jobs?q={kw}&page={page}"
_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_SALARY_TYPE = {"per_year": "年薪", "per_month": "月薪", "per_day": "日薪", "per_hour": "時薪"}


def _format_salary(s) -> str | None:
    """Cake salary：{min, max, currency, type} → 可讀字串。"""
    if not isinstance(s, dict):
        return None
    try:
        lo = int(s.get("min") or 0)
        hi = int(s.get("max") or 0)
    except (TypeError, ValueError):
        return None
    if not lo and not hi:
        return None
    cur = s.get("currency") or ""
    label = _SALARY_TYPE.get(s.get("type") or "", "")
    if lo and hi and lo != hi:
        amount = f"{cur} {lo:,}–{hi:,}"
    elif hi:
        amount = f"{cur} {hi:,}"
    else:
        amount = f"{cur} {lo:,} 以上"
    return f"{label} {amount}".strip()


def search(keywords: str, limit: int = 15, pages: int = 1) -> SearchResult:
    """搜尋 Cake；pages>1 時逐頁抓取（網址帶 page 參數）並跨頁去重。"""
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    cap = limit * max(1, pages)
    first_error = None
    for pg in range(1, max(1, pages) + 1):
        try:
            r = http_get(_PAGE.format(kw=quote(keywords), page=pg), verify=False)
            if not r.ok:
                first_error = f"HTTP {r.status_code}"
                break
            m = _NEXT.search(r.text)
            if not m:
                first_error = "找不到 __NEXT_DATA__"
                break
            data = json.loads(m.group(1))
            entities = (data.get("props", {}).get("pageProps", {})
                        .get("initialState", {}).get("jobSearch", {}).get("entityByPathId", {}))
        except Exception as e:
            first_error = str(e)[:150]
            break

        before = len(jobs)
        for d in (entities or {}).values():
            if not isinstance(d, dict) or not d.get("title") or not d.get("path"):
                continue
            page = d.get("page") if isinstance(d.get("page"), dict) else {}
            company_path = page.get("path") or ""
            url = (f"https://www.cake.me/companies/{company_path}/jobs/{d['path']}"
                   if company_path else f"https://www.cake.me/jobs/{d['path']}")
            if url in seen:
                continue
            seen.add(url)
            locs = d.get("locations") or []
            location = "、".join(str(x) for x in locs) if isinstance(locs, list) else None
            tags = d.get("tags") or []
            jobs.append(JobPosting(
                source=NAME,
                title=clean(d.get("title") or ""),
                company=clean(page.get("name") or ""),
                location=clean(location) or None,
                salary=_format_salary(d.get("salary")),
                url=url,
                snippet=clean((d.get("description") or "")[:200]) or None,
                requirements=[str(t) for t in tags][:10] if isinstance(tags, list) else [],
            ))
            if len(jobs) >= cap:
                break
        if len(jobs) >= cap or len(jobs) - before == 0:
            break  # 已達上限，或這一頁沒有新職缺 → 停止翻頁
    if not jobs:
        return SearchResult(source=NAME, blocked=True, error=first_error or "解析不到職缺")
    return SearchResult(source=NAME, jobs=jobs)
