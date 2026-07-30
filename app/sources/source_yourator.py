"""Yourator：v4 jobs JSON API；TLS 驗證失敗時安全降級為 blocked。"""
from __future__ import annotations

from urllib.parse import quote

from bs4 import BeautifulSoup

from app.models import JobPosting, SearchResult
from app.sources.base import clean, http_get
from app.sources.work_mode import filter_jobs_by_work_mode, infer_work_mode

NAME = "yourator"
SEARCHABLE = True
_API = "https://www.yourator.co/api/v4/jobs?term[]={kw}&page={page}"
_REMOTE_API = "https://www.yourator.co/api/v4/events/71/jobs?term[]={kw}&page={page}"
_DETAIL_BUDGET = 12  # 遠端型態只在詳情頁；限制額外請求，維持個人低頻使用。


def _tag_work_mode(tags: list[object]) -> str:
    """Yourator 的職缺 tags 是來源端結構化標籤，可視為來源明確標示。"""
    mode = infer_work_mode(" ".join(str(t) for t in tags))
    return mode if mode in {"remote", "hybrid"} else "unknown"


def _detail_work_mode(url: str) -> str:
    """從 Yourator 詳情頁「遠端型態」區塊讀取工作型態；忽略只描述面試的標籤。"""
    try:
        r = http_get(url)
        if not r.ok:
            return "unknown"
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return "unknown"
    for el in soup.select(".remote-content strong"):
        label = clean(el.get_text(" ", strip=True))
        lower = label.lower()
        if "面試" in label or "interview" in lower:
            continue
        mode = infer_work_mode(label)
        if mode in {"remote", "hybrid"}:
            return mode
        if "remote job" in lower:
            return "remote"
    return "unknown"


def search(keywords: str, limit: int = 15, pages: int = 1,
           area: list[str] | None = None, work_modes: list[str] | None = None,
           include_inferred: bool = False) -> SearchResult:
    """搜尋 Yourator；pages>1 時逐頁抓取（API 吃 page 參數）並跨頁去重。

    area：保留參數，本來源不支援來源端地區篩選（地區由結果端 location 過濾處理）。
    work_modes：先查 Yourator 官方遠端職缺專區；列表未帶遠端型態時，有限度讀詳情頁。
    """
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    any_response = False
    first_error: str | None = None
    detail_budget = _DETAIL_BUDGET if work_modes else 0
    api = _REMOTE_API if work_modes else _API
    for page in range(1, max(1, pages) + 1):
        try:
            r = http_get(api.format(kw=quote(keywords), page=page))
            if not r.ok:
                if page == 1 and first_error is None:
                    first_error = f"HTTP {r.status_code}"
                break
            any_response = True
            data = (r.json().get("payload") or {}).get("jobs") or []
        except Exception as e:
            if page == 1 and first_error is None:
                first_error = str(e)[:150]
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
            tag_mode = _tag_work_mode(tags if isinstance(tags, list) else [])
            job = JobPosting(
                source=NAME,
                title=d.get("name", ""),
                company=comp.get("brand") or comp.get("enName") or "",
                location=d.get("location"),
                salary=d.get("salary"),
                url=url,
                snippet="、".join(tags) if tags else None,
                requirements=tags,
                work_mode=tag_mode,
                work_mode_origin="source" if tag_mode != "unknown" else "unknown",
            )
            needs_source_confirmation = (
                job.work_mode_origin != "source"
                and (not include_inferred or job.work_mode == "unknown")
            )
            if work_modes and needs_source_confirmation and detail_budget > 0 and url:
                detail_budget -= 1
                detail_mode = _detail_work_mode(url)
                if detail_mode != "unknown":
                    job.work_mode = detail_mode
                    job.work_mode_origin = "source"
            jobs.append(job)

    jobs = filter_jobs_by_work_mode(
        jobs,
        work_modes,
        include_inferred=include_inferred,
    )
    if not any_response:
        return SearchResult(source=NAME, blocked=True, error=first_error or "解析不到職缺")
    return SearchResult(source=NAME, jobs=jobs)
