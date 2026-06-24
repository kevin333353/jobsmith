"""職缺來源註冊表：彙整多站搜尋、LinkedIn 深連結。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from app.models import SearchResult
from app.sources import source_104, source_yourator, source_linkedin, source_cake

# 可關鍵字搜尋的來源（name -> search 函式）
SEARCHABLE = {
    source_104.NAME: source_104.search,
    source_yourator.NAME: source_yourator.search,
    source_linkedin.NAME: source_linkedin.search,
    source_cake.NAME: source_cake.search,
}

# 尚未穩定、暫不啟用的來源（UI 標「即將支援」，避免永遠失敗的來源傷可信度）。
COMING_SOON: dict[str, str] = {}


def search_all(keywords: str, sources: list[str] | None = None, limit: int = 15) -> list[SearchResult]:
    """對選定來源『並行』各跑一次搜尋；單一來源失敗只回該來源 blocked，不影響其他。

    結果固定依 names 的順序回傳（與並行無關），方便上層彙整與測試。
    """
    names = [n for n in (sources or list(SEARCHABLE)) if n in SEARCHABLE]
    if not names:
        return []
    out: dict[str, SearchResult] = {}
    with ThreadPoolExecutor(max_workers=len(names)) as ex:
        futs = {ex.submit(SEARCHABLE[n], keywords, limit): n for n in names}
        for fut in as_completed(futs):
            n = futs[fut]
            try:
                out[n] = fut.result()
            except Exception as e:  # noqa: BLE001 — 單一來源失敗不影響其他
                out[n] = SearchResult(source=n, blocked=True, error=str(e)[:150])
    return [out[n] for n in names]


def linkedin_search_url(keywords: str) -> str:
    """LinkedIn 不爬整頁：產生預填關鍵字的台灣職缺搜尋深連結。"""
    return f"https://www.linkedin.com/jobs/search/?keywords={quote(keywords)}&location=Taiwan"
