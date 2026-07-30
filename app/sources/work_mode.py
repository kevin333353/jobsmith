"""職缺工作型態正規化與篩選。

來源有明確欄位／官方篩選時標為 ``source``；只有標題、標籤或 JD 文字可判斷時
標為 ``inferred``。模糊的「遠端工作」不直接當成完全遠端，避免過度承諾。
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.models import JobPosting

WorkMode = Literal["remote", "hybrid", "onsite", "unknown"]
WorkModeOrigin = Literal["source", "inferred", "unknown"]
FILTERABLE_WORK_MODES = {"remote", "hybrid"}

_ONSITE_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\bno[\s-]+remote\b",
    r"\bon[\s-]*site\b",
    r"不(?:提供|開放|接受|支援).{0,8}(?:遠端|遠距|居家)",
    r"(?:無|沒有).{0,4}(?:遠端|遠距|居家)",
    r"(?:需|須)(?:每日|全程)?(?:到|進)(?:公司|辦公室|現場)",
    r"全程(?:現場|到班|進辦公室)",
))

_HYBRID_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\bhybrid\b",
    r"\bpartial(?:ly)?[\s-]+remote\b",
    r"\boptional[\s-]+remote\b",
    r"\bremote[\s-]+friendly\b",
    r"部分\s*(?:遠端|遠距|居家)",
    r"混合(?:式)?\s*(?:辦公|工作|上班)",
    r"(?:彈性|可選|可申請|可安排).{0,10}(?:遠端|遠距|居家)",
    r"(?:每週|每周).{0,12}(?:天|日).{0,12}(?:遠端|遠距|居家)",
))

_REMOTE_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"100\s*%\s*(?:remote|遠端|遠距|居家)",
    r"\b(?:fully|full)[\s-]+remote\b",
    r"\bremote[\s-]+only\b",
    r"\bwork[\s-]+from[\s-]+anywhere\b",
    r"(?:完全|全程|全職)\s*(?:遠端|遠距|居家)",
    r"全\s*(?:遠端|遠距)",
    r"(?:不需|不用|不必).{0,8}(?:到|進).{0,8}(?:公司|辦公室)",
    r"[\[(（【]\s*remote\s*[\])）】]",
))

_INTERVIEW_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"(?:部分|完全|全程)?\s*(?:遠端|遠距|線上)\s*(?:面試|面談)",
    r"\b(?:remote|hybrid|online)[\s-]+interview\b",
    r"\binterview.{0,10}(?:remote|hybrid|online)\b",
))


def infer_work_mode(*values: object) -> WorkMode:
    """由文字保守推測工作型態；沒有強證據就回 ``unknown``。"""
    text = " ".join(str(v).strip() for v in values if v is not None and str(v).strip())
    if not text:
        return "unknown"
    for pattern in _INTERVIEW_PATTERNS:
        text = pattern.sub(" ", text)
    if any(p.search(text) for p in _ONSITE_PATTERNS):
        return "onsite"
    if any(p.search(text) for p in _HYBRID_PATTERNS):
        return "hybrid"
    if any(p.search(text) for p in _REMOTE_PATTERNS):
        return "remote"
    return "unknown"


def parse_work_modes(raw: str | None) -> list[str]:
    """前端逗號字串 → 有效且去重的遠端篩選值。"""
    out: list[str] = []
    for part in (raw or "").split(","):
        mode = part.strip().lower()
        if mode in FILTERABLE_WORK_MODES and mode not in out:
            out.append(mode)
    return out


def filter_jobs_by_work_mode(
    jobs: list["JobPosting"],
    modes: list[str] | None,
    *,
    include_inferred: bool = False,
) -> list["JobPosting"]:
    """依工作型態過濾；嚴格模式只接受來源明確標示的職缺。"""
    wanted = {m for m in (modes or []) if m in FILTERABLE_WORK_MODES}
    if not wanted:
        return list(jobs)
    return [
        job for job in jobs
        if job.work_mode in wanted
        and (job.work_mode_origin == "source" or include_inferred)
    ]
