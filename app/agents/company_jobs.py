"""公司職缺查詢：① job boards 依公司名過濾 + ② claude_cli WebSearch 找官網 careers 開缺，合併去重。

② 走 research_structured（僅 claude_cli 後端有上網工具）；其他後端則只回 ① 的 boards 結果。
"""
from __future__ import annotations

from app.llm import research_structured
from app.models import JobPosting, JobPostingList
from app.sources.registry import search_all

_BOARD_SOURCES = {"104", "yourator", "linkedin", "cake"}

CAREERS_SYSTEM = (
    "你是求職研究員。請用網路搜尋找出指定公司的『官方 careers / 徵才頁』目前正在開的職缺，"
    "每筆含 title、company、url（必須指向公司官網或其使用的 ATS 職缺頁，例如 greenhouse/lever）、"
    "location（若有）。若官方頁明確標示工作型態，work_mode 填 remote / hybrid / onsite，"
    "否則填 unknown；不要靠猜測。只回實際查到的職缺，不要臆造；source 一律填 careers。"
)


def _norm(s: str) -> str:
    return "".join(str(s).lower().split())


def _company_match(job_company: str, target: str) -> bool:
    a, b = _norm(job_company), _norm(target)
    return bool(a) and (a in b or b in a)


def find_company_jobs(
    company: str,
    profile=None,
    work_modes: list[str] | None = None,
    include_inferred: bool = False,
) -> list[JobPosting]:
    seen: set[str] = set()
    out: list[JobPosting] = []

    # ① job boards 依公司名過濾
    try:
        search_kwargs = {}
        if work_modes:
            search_kwargs = {
                "work_modes": work_modes,
                "include_inferred": include_inferred,
            }
        for res in search_all(company, limit=15, **search_kwargs):
            for j in res.jobs:
                if _company_match(j.company, company):
                    key = j.url or (j.title + j.company)
                    if key not in seen:
                        seen.add(key)
                        out.append(j)
    except Exception:
        pass

    # ② WebSearch 官網 careers（僅 claude_cli 後端；其他回 None）
    try:
        result = research_structured(
            JobPostingList,
            [("system", CAREERS_SYSTEM),
             ("human", (
                 f"公司名稱：{company}\n請找出這家公司官方 careers 頁目前的開缺。"
                 + (f"\n優先找工作型態為：{'、'.join(work_modes)}。" if work_modes else "")
             ))],
            tier="standard",
        )
    except Exception:
        result = None
    if result is not None:
        for j in (result.items or []):
            if not j.title or not j.url:
                continue
            if j.source not in _BOARD_SOURCES:
                j.source = "careers"
            key = j.url or (j.title + j.company)
            if key not in seen:
                seen.add(key)
                out.append(j)

    return out
