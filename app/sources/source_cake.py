"""Cake（cake.me）：解析搜尋頁 __NEXT_DATA__ 的 initialState.jobSearch.entityByPathId。

Cake 已改用 Algolia client-side 搜尋，但 SSR 仍把首頁結果放進 __NEXT_DATA__ 的
initialState.jobSearch.entityByPathId（slug -> 職缺）。TLS 驗證失敗即安全降級。
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from app.models import JobPosting, SearchResult
from app.sources.base import clean, http_get
from app.sources.work_mode import filter_jobs_by_work_mode

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


def _search_variants(
    work_modes: list[str] | None,
    include_inferred: bool,
) -> list[tuple[str, str | None]]:
    modes = set(work_modes or [])
    if not modes:
        return [("", None)]
    variants: list[tuple[str, str | None]] = []
    if "remote" in modes:
        variants.append(("&remote=full_remote_work", "remote"))
    if "hybrid" in modes:
        variants.append(("&remote=partial_remote_work%2Coptional_remote_work", "hybrid"))
    if include_inferred:
        variants.append(("", None))
    return variants


def search(keywords: str, limit: int = 15, pages: int = 1,
           area: list[str] | None = None, work_modes: list[str] | None = None,
           include_inferred: bool = False) -> SearchResult:
    """搜尋 Cake；pages>1 時逐頁抓取（網址帶 page 參數）並跨頁去重。

    area：保留參數，本來源不支援來源端地區篩選（地區由結果端 location 過濾處理）。
    work_modes：以 Cake 官方 full/partial/optional remote 篩選分開查詢並標記來源依據。
    """
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    cap = limit * max(1, pages)
    first_error: str | None = None
    any_parsed_response = False
    for mode_q, confirmed_mode in _search_variants(work_modes, include_inferred):
        variant_added = 0
        for pg in range(1, max(1, pages) + 1):
            try:
                r = http_get(_PAGE.format(kw=quote(keywords), page=pg) + mode_q)
                if not r.ok:
                    if first_error is None:
                        first_error = f"HTTP {r.status_code}"
                    break
                m = _NEXT.search(r.text)
                if not m:
                    if first_error is None:
                        first_error = "找不到 __NEXT_DATA__"
                    break
                data = json.loads(m.group(1))
                entities = (data.get("props", {}).get("pageProps", {})
                            .get("initialState", {}).get("jobSearch", {}).get("entityByPathId", {}))
                any_parsed_response = True
            except Exception as e:
                if first_error is None:
                    first_error = str(e)[:150]
                break

            before = variant_added
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
                    work_mode=confirmed_mode or "unknown",
                    work_mode_origin="source" if confirmed_mode else "unknown",
                ))
                variant_added += 1
                if variant_added >= cap:
                    break
            if variant_added >= cap or variant_added - before == 0:
                break  # 已達上限，或這一頁沒有新職缺 → 停止翻頁

    jobs = filter_jobs_by_work_mode(
        jobs,
        work_modes,
        include_inferred=include_inferred,
    )
    if not jobs and (not any_parsed_response or not work_modes):
        return SearchResult(source=NAME, blocked=True, error=first_error or "解析不到職缺")
    return SearchResult(source=NAME, jobs=jobs)
