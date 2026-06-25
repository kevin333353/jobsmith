"""LinkedIn：免登入 guest jobs API（低頻、personal 用，與 104 同立場）。

端點 jobs-guest/.../seeMoreJobPostings/search 回傳職缺卡 HTML，免登入。
本機對 linkedin.com 憑證鏈驗證失敗（同 yourator/cake），故 verify=False 取公開唯讀資料。
"""
from __future__ import annotations

from urllib.parse import quote

from bs4 import BeautifulSoup

from app.models import JobPosting, SearchResult
from app.sources.base import clean, http_get

NAME = "linkedin"
SEARCHABLE = True
_API = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        "?keywords={kw}&location=Taiwan&start={start}")
_PER_PAGE = 25  # guest API 每次回傳一批，下一頁以 start 位移 25


def search(keywords: str, limit: int = 15, pages: int = 1) -> SearchResult:
    """搜尋 LinkedIn guest API；pages>1 時以 start 位移逐頁抓取並跨頁去重。"""
    jobs: list[JobPosting] = []
    seen: set[str] = set()
    cap = limit * max(1, pages)  # 總筆數上限，與其他來源的 limit×pages 一致
    for page in range(max(1, pages)):
        try:
            r = http_get(_API.format(kw=quote(keywords), start=page * _PER_PAGE), verify=False)
            if not r.ok:
                if page == 0:
                    return SearchResult(source=NAME, blocked=True, error=f"HTTP {r.status_code}")
                break
        except Exception as e:  # 連線/憑證錯誤 → 降級
            if page == 0:
                return SearchResult(source=NAME, blocked=True, error=str(e)[:150])
            break

        soup = BeautifulSoup(r.text, "html.parser")
        before = len(jobs)
        for card in soup.select("div.base-card"):
            title_el = card.select_one(".base-search-card__title")
            if not title_el:
                continue
            comp_el = card.select_one(".base-search-card__subtitle")
            loc_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")
            url = ((link_el.get("href") if link_el else "") or "").split("?")[0]
            key = url or clean(title_el.get_text(strip=True))
            if key in seen:
                continue
            seen.add(key)
            jobs.append(JobPosting(
                source=NAME,
                title=clean(title_el.get_text(strip=True)),
                company=clean(comp_el.get_text(strip=True)) if comp_el else "",
                location=clean(loc_el.get_text(strip=True)) if loc_el else None,
                url=url,
                snippet=None,
            ))
            if len(jobs) >= cap:
                break
        if len(jobs) >= cap or len(jobs) - before == 0:
            break  # 已達上限，或這一頁沒有新職缺 → 停止翻頁
    if not jobs:
        return SearchResult(source=NAME, blocked=True, error="解析不到職缺")
    return SearchResult(source=NAME, jobs=jobs)
