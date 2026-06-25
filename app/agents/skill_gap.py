"""技能缺口市場分析：從搜到的職缺萃取技能需求，對照履歷找出缺口。

無 LLM（便宜、可測、確定性）。關鍵設計：
1. 需求來源是職缺的『標題 + 摘要 + requirements』經技能詞庫萃取，而非只看 requirements 欄位——
   104 / LinkedIn 幾乎不填 requirements，只看該欄位會讓主要來源零貢獻、缺口只反映 cake/yourator
   的少量 tag；且 tag 常混入「Full-time / Remote」等雜訊，詞庫萃取會自動濾掉。見 skill_lexicon。
2. 「已具備」比對的對象是整份履歷（技能 + 摘要 + 經歷 + 期望職務）同樣經詞庫萃取——
   履歷寫「機器學習」即視為具備 canonical「machine learning」，免英中對不上。
3. 來源職缺應由呼叫端先篩成「與履歷相關」的（高適配），避免無關職缺的技能污染缺口清單。
"""
from __future__ import annotations

from collections import Counter

from app.agents.skill_lexicon import extract_skills
from app.models import Profile, JobPosting, SkillCount, SkillGapReport


def _norm(s: str) -> str:
    """小寫 + 收斂空白。"""
    return " ".join(str(s).lower().split())


def _profile_blob(profile: Profile) -> str:
    """整份履歷的可比對文字（技能 + 摘要 + 經歷 + 期望職務），正規化成一個字串。"""
    parts: list[str] = list(profile.skills or [])
    if profile.summary:
        parts.append(profile.summary)
    parts += list(profile.preferred_roles or [])
    parts += list(profile.experiences or [])
    return _norm(" \n ".join(parts))


def _job_text(j: JobPosting) -> str:
    """單一職缺的可萃取文字：標題 + 摘要 + requirements（涵蓋沒填 requirements 的來源）。"""
    parts = [j.title or "", j.snippet or "", " ".join(str(r) for r in (j.requirements or []))]
    return " ".join(p for p in parts if p)


def analyze_skill_gap(profile: Profile, jobs: list[JobPosting], top_n: int = 15) -> SkillGapReport:
    have_set = set(extract_skills(_profile_blob(profile)))  # 履歷本身具備的技能（canonical）
    counter: Counter[str] = Counter()
    for j in jobs:
        for skill in set(extract_skills(_job_text(j))):  # 每職缺每技能只計一次
            counter[skill] += 1
    ranked = counter.most_common()
    top_demand = [SkillCount(skill=k, count=c) for k, c in ranked[:top_n]]
    your_gaps = [SkillCount(skill=k, count=c) for k, c in ranked if k not in have_set][:top_n]
    have = [k for k, _ in ranked if k in have_set]
    return SkillGapReport(top_demand=top_demand, your_gaps=your_gaps, have=have)
