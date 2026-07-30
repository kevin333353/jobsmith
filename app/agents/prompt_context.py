"""共用 prompt 上下文：避免每個 agent 重複吞下完整履歷原文。"""
from __future__ import annotations

import json
import re

from app.models import ParsedJob, Profile

_MAX_EVIDENCE_CHARS = 6000
_MAX_FALLBACK_CHARS = 4000


def _resume_lines(raw_text: str) -> list[str]:
    """把履歷原文切成可排序的證據行；過長單行再依句號切分。"""
    raw_lines = [line.strip() for line in re.split(r"[\r\n]+", raw_text) if line.strip()]
    if len(raw_lines) <= 1 and raw_lines and len(raw_lines[0]) > 500:
        raw_lines = [
            part.strip()
            for part in re.split(r"(?<=[。！？.!?；;])\s*", raw_lines[0])
            if part.strip()
        ]
    seen: set[str] = set()
    out: list[str] = []
    for line in raw_lines:
        compact = re.sub(r"\s+", " ", line)
        key = compact.casefold()
        if key not in seen:
            seen.add(key)
            out.append(compact)
    return out


def _job_terms(job: ParsedJob) -> set[str]:
    phrases = [
        job.title,
        *job.required_skills,
        *job.tech_stack,
        *job.nice_to_have,
    ]
    terms: set[str] = set()
    for phrase in phrases:
        value = phrase.strip().casefold()
        if not value:
            continue
        terms.add(value)
        terms.update(
            token for token in re.findall(r"[a-z0-9+#.-]{2,}", value)
            if len(token) >= 2
        )
    return terms


def relevant_resume_evidence(
    raw_text: str,
    job: ParsedJob,
    max_chars: int = _MAX_EVIDENCE_CHARS,
) -> str:
    """挑出與 JD 最相關、具數字成果的原文行，並維持履歷原順序。

    這不是摘要模型呼叫：純本機排序，既保留不可捏造的原始證據，也避免把整份 raw_text
    在匹配、履歷、求職信與面試四個 prompt 中重複傳送。
    """
    lines = _resume_lines(raw_text)
    if not lines or max_chars <= 0:
        return ""
    terms = _job_terms(job)
    ranked: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        folded = line.casefold()
        score = sum(4 for term in terms if term in folded)
        if re.search(r"\d", line):
            score += 2
        if any(mark in folded for mark in ("%", "提升", "降低", "節省", "成長", "built", "led", "improved")):
            score += 1
        ranked.append((score, index, line))

    relevant = [item for item in ranked if item[0] > 0]
    if not relevant:
        relevant = ranked[:20]
    # 先取高相關行，再恢復原始順序，讓模型仍看得懂經歷脈絡。
    chosen: list[tuple[int, str]] = []
    used = 0
    for _, index, line in sorted(relevant, key=lambda item: (-item[0], item[1])):
        cost = len(line) + 1
        if chosen and used + cost > max_chars:
            continue
        chosen.append((index, line[:max_chars]))
        used += min(cost, max_chars)
        if used >= max_chars:
            break
    return "\n".join(line for _, line in sorted(chosen))[:max_chars]


def profile_prompt_json(
    profile: Profile,
    *,
    job: ParsedJob | None = None,
    include_relevant_raw: bool = False,
) -> str:
    """輸出 prompt 用精簡 Profile JSON。

    正常情況排除 raw_text 與內部降級旗標；履歷客製只附 JD 相關證據。若結構化解析幾乎
    沒有內容，才附一小段原文後備，避免降級 Profile 完全失去求職者資訊。
    """
    data = profile.model_dump(exclude={"raw_text", "parse_degraded"}, exclude_none=True)
    if include_relevant_raw and job is not None and profile.raw_text:
        evidence = relevant_resume_evidence(profile.raw_text, job)
        if evidence:
            data["relevant_resume_evidence"] = evidence
    elif not profile.skills and not profile.experiences and profile.raw_text:
        data["resume_excerpt"] = profile.raw_text.strip()[:_MAX_FALLBACK_CHARS]
    return json.dumps(data, ensure_ascii=False, indent=2)
