"""104 人力銀行：前端搜尋 JSON API（需帶 Referer）。個人使用、低頻、被擋即降級。"""
from __future__ import annotations

from urllib.parse import quote

from app.models import JobPosting, SearchResult
from app.sources.base import clean, http_get
from app.sources.work_mode import filter_jobs_by_work_mode

NAME = "104"
SEARCHABLE = True
_REFERER = "https://www.104.com.tw/jobs/search/"
_API = ("https://www.104.com.tw/jobs/search/api/jobs?ro=0&kwop=7&keyword={kw}"
        "&order=15&asc=0&page={page}&mode=s&jobsource=2018indexpoc")


# 104 薪資型態碼（欄位 s10）。salaryDesc 已不再回傳，真值在 salaryLow/salaryHigh。
_SALARY_TYPE = {10: "面議", 30: "時薪", 40: "日薪", 50: "月薪", 60: "年薪"}


def _format_salary(d: dict) -> str | None:
    """由 salaryLow/salaryHigh + 型態碼 s10 組出可讀薪資字串。"""
    try:
        low = int(d.get("salaryLow") or 0)
        high = int(d.get("salaryHigh") or 0)
    except (TypeError, ValueError):
        low = high = 0
    if high >= 9_999_999:  # 104「X 元以上」開放上限的哨兵值 → 視為無上限
        high = 0
    try:
        code = int(d.get("s10") or 0)
    except (TypeError, ValueError):
        code = 0
    if code == 10 or (low == 0 and high == 0):
        return "面議"
    label = _SALARY_TYPE.get(code, "")
    if low and high and low != high:
        amount = f"NT${low:,}–{high:,}"
    elif high:
        amount = f"NT${high:,}"
    elif low:
        amount = f"NT${low:,} 以上"
    else:
        return "面議"
    return f"{label} {amount}".strip()


def _tag_texts(d: dict) -> list[str]:
    """收斂 104 搜尋卡可能回傳的字串或物件標籤。"""
    out: list[str] = []
    for tag in d.get("tags") or []:
        if isinstance(tag, dict):
            value = tag.get("description") or tag.get("desc") or tag.get("name")
        else:
            value = tag
        text = clean(value or "")
        if text:
            out.append(text)
    return out


def _search_variants(
    work_modes: list[str] | None,
    include_inferred: bool,
) -> list[tuple[str, str | None]]:
    modes = set(work_modes or [])
    if not modes:
        return [("", None)]
    variants: list[tuple[str, str | None]] = []
    if "remote" in modes:
        variants.append(("&remoteWork=1", "remote"))
    # 104 沒有可驗證的「部分遠端」來源端分類；允許文字推測時才補抓一般結果。
    if include_inferred:
        variants.append(("", None))
    return variants


def search(keywords: str, limit: int = 15, pages: int = 1,
           area: list[str] | None = None, work_modes: list[str] | None = None,
           include_inferred: bool = False) -> SearchResult:
    """搜尋 104；pages>1 時逐頁抓取（API 吃 page 參數）並跨頁去重。

    area：104 地區代碼清單（來源端篩選，逗號串接帶入 &area=）；空則不限地區。
    work_modes：完全遠端使用官方 remoteWork=1；部分遠端僅能由 JD 文字保守推測。
    blocked 僅看第一頁：第一頁失敗才降級；後續頁失敗就停在已收到的結果。
    """
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    area_q = ("&area=" + quote(",".join(area))) if area else ""
    any_response = False
    first_error: str | None = None
    variants = _search_variants(work_modes, include_inferred)
    if not variants:
        return SearchResult(source=NAME)

    for mode_q, confirmed_mode in variants:
        for page in range(1, max(1, pages) + 1):
            try:
                r = http_get(
                    _API.format(kw=quote(keywords), page=page) + area_q + mode_q,
                    referer=_REFERER,
                )
                if not r.ok:
                    if page == 1 and first_error is None:
                        first_error = f"HTTP {r.status_code}"
                    break
                any_response = True
                data = r.json().get("data") or []
            except Exception as e:  # 連線/解析錯誤 → 降級
                if page == 1 and first_error is None:
                    first_error = str(e)[:150]
                break
            if not data:
                break  # 沒有更多職缺，提早停止翻頁
            for d in data[:limit]:
                link = d.get("link") or {}
                url = link.get("job", "") or ""
                key = url or (d.get("jobName", "") + d.get("custName", ""))
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(JobPosting(
                    source=NAME,
                    title=clean(d.get("jobName", "")),
                    company=clean(d.get("custName", "")),
                    location=d.get("jobAddrNoDesc") or d.get("jobAddress"),
                    salary=_format_salary(d),
                    url=url,
                    snippet=clean(d.get("descSnippet") or d.get("description") or ""),
                    requirements=_tag_texts(d),
                    work_mode=confirmed_mode or "unknown",
                    work_mode_origin="source" if confirmed_mode else "unknown",
                ))

    jobs = filter_jobs_by_work_mode(
        jobs,
        work_modes,
        include_inferred=include_inferred,
    )
    if not any_response and first_error:
        return SearchResult(source=NAME, blocked=True, error=first_error)
    return SearchResult(source=NAME, jobs=jobs)
