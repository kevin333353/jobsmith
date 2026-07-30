"""職缺來源註冊表：彙整多站搜尋、LinkedIn 深連結。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from app.models import SearchResult
from app.sources import source_104, source_cake, source_linkedin, source_yourator

# 可關鍵字搜尋的來源（name -> search 函式）
SEARCHABLE = {
    source_104.NAME: source_104.search,
    source_yourator.NAME: source_yourator.search,
    source_linkedin.NAME: source_linkedin.search,
    source_cake.NAME: source_cake.search,
}

# 尚未穩定、暫不啟用的來源（UI 標「即將支援」，避免永遠失敗的來源傷可信度）。
COMING_SOON: dict[str, str] = {}


def search_all(keywords: str, sources: list[str] | None = None, limit: int = 15,
               pages: int = 1, area: list[str] | None = None,
               work_modes: list[str] | None = None,
               include_inferred: bool = False) -> list[SearchResult]:
    """對選定來源『並行』各跑一次搜尋；單一來源失敗只回該來源 blocked，不影響其他。

    pages>1 時各來源逐頁抓取（每來源最多約 limit×pages 筆）。
    area：地區代碼清單，傳給各來源（目前 104 於來源端篩選，其餘來源忽略、由上層結果端過濾）。
    work_modes：遠端型態清單；有設定時才傳給新版來源介面，維持舊呼叫/測試相容。
    結果固定依 names 的順序回傳（與並行無關），方便上層彙整與測試。
    """
    names = [n for n in (sources or list(SEARCHABLE)) if n in SEARCHABLE]
    if not names:
        return []
    out: dict[str, SearchResult] = {}
    with ThreadPoolExecutor(max_workers=len(names)) as ex:
        if work_modes:
            futs = {
                ex.submit(
                    SEARCHABLE[n],
                    keywords,
                    limit,
                    pages,
                    area,
                    work_modes,
                    include_inferred,
                ): n
                for n in names
            }
        else:
            futs = {ex.submit(SEARCHABLE[n], keywords, limit, pages, area): n for n in names}
        for fut in as_completed(futs):
            n = futs[fut]
            try:
                out[n] = fut.result()
            except Exception as e:  # noqa: BLE001 — 單一來源失敗不影響其他
                out[n] = SearchResult(source=n, blocked=True, error=str(e)[:150])
    return [out[n] for n in names]


def linkedin_search_url(
    keywords: str,
    location: str = "Taiwan",
    work_modes: list[str] | None = None,
) -> str:
    """LinkedIn 不爬整頁：產生預填關鍵字（與地區）的職缺搜尋深連結。"""
    url = f"https://www.linkedin.com/jobs/search/?keywords={quote(keywords)}&location={quote(location)}"
    codes = [code for mode, code in (("remote", "2"), ("hybrid", "3"))
             if mode in set(work_modes or [])]
    return url + (f"&f_WT={quote(','.join(codes))}" if codes else "")
