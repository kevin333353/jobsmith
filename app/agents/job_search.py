"""職缺探索 agent：從履歷推導搜尋關鍵字、對搜到的職缺依履歷排序。"""
from pydantic import BaseModel, Field, field_validator

from app.llm import get_llm
from app.models import JobMatch, JobPosting, Profile, coerce_str, coerce_str_list

QUERY_SYSTEM = (
    "你是台灣求職顧問。根據求職者背景，產出 1-3 個最適合在台灣求職網站（104/Cake/Yourator）"
    "搜尋的『關鍵字詞』（每個 2-8 字，例如『AI 工程師』『Python 後端』『LLM 應用』）。"
    "以求職者的核心技能與期望職務為準，由廣到精，不要太長。"
)

RANK_SYSTEM = (
    "你是台灣求職顧問。下面是求職者背景與一批職缺清單（每筆有索引）。"
    "請對『每一筆』職缺評估與求職者的適配分數（fit_score 0-100），"
    "並列出符合點(matched)、落差點(gaps)、一句適配理由(reason)。"
    "務實評分：技能/年資/領域吻合度高才給高分。全程繁體中文。"
)


class SearchQueries(BaseModel):
    queries: list[str] = Field(default_factory=list, description="1-3 個搜尋關鍵字詞")

    # codex/gpt 可能把 queries 回成 null 或單一字串，先收斂避免結構化解析失敗。
    @field_validator("queries", mode="before")
    @classmethod
    def _coerce_queries(cls, v):
        return coerce_str_list(v)


class _RankItem(BaseModel):
    index: int = Field(description="對應職缺清單的索引")
    fit_score: int = Field(ge=0, le=100)
    matched: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    reason: str = ""

    @field_validator("matched", "gaps", mode="before")
    @classmethod
    def _coerce_lists(cls, v):
        return coerce_str_list(v)

    @field_validator("reason", mode="before")
    @classmethod
    def _coerce_reason(cls, v):
        return coerce_str(v)


class _RankResult(BaseModel):
    rankings: list[_RankItem] = Field(default_factory=list)

    @field_validator("rankings", mode="before")
    @classmethod
    def _coerce_rankings(cls, v):
        return v if v is not None else []


def _profile_brief(profile: Profile) -> str:
    """精簡的求職者描述（不含 raw_text 全文，控制 prompt 大小）。"""
    return (
        f"姓名：{profile.name}\n定位：{profile.summary}\n"
        f"技能：{'、'.join(profile.skills) or '（無）'}\n"
        f"經歷：{'；'.join(profile.experiences) or '（無）'}\n"
        f"年資：{profile.years_experience}\n"
        f"期望職務：{'、'.join(profile.preferred_roles) or '（無）'}"
    )


def derive_queries(profile: Profile) -> list[str]:
    """從履歷推導搜尋關鍵字（cheap 分層）。"""
    llm = get_llm("cheap").with_structured_output(SearchQueries)
    out = llm.invoke([("system", QUERY_SYSTEM), ("human", _profile_brief(profile))])
    queries = [q.strip() for q in out.queries if q.strip()][:3]
    if queries:
        return queries
    # 後備：用期望職務或首要技能
    if profile.preferred_roles:
        return [profile.preferred_roles[0]]
    if profile.skills:
        return [profile.skills[0]]
    return ["工程師"]


_RANK_INPUT_MAX = 50  # 送 LLM 排序的職缺上限（控 prompt 大小/成本）；超出者不送排序


def rank_jobs(profile: Profile, jobs: list[JobPosting], top_k: int | None = None) -> list[JobMatch]:
    """以一次 LLM 呼叫對職缺評分排序（standard 分層）。

    top_k=None（預設）回傳全部排序結果（不截斷，由前端分頁）；為控 prompt，最多送
    _RANK_INPUT_MAX 筆給 LLM 排序，超出部分以 fit_score=0 附在後面。
    """
    if not jobs:
        return []
    ranked_pool, overflow = jobs[:_RANK_INPUT_MAX], jobs[_RANK_INPUT_MAX:]
    jobs = ranked_pool
    listing = "\n".join(
        f"[{i}] {j.title} @ {j.company}｜{j.location or ''}｜{(j.snippet or '')[:120]}"
        for i, j in enumerate(jobs)
    )
    llm = get_llm("standard", max_tokens=4000).with_structured_output(_RankResult)
    human = f"【求職者】\n{_profile_brief(profile)}\n\n【職缺清單】\n{listing}"
    out = llm.invoke([("system", RANK_SYSTEM), ("human", human)])
    by_idx = {r.index: r for r in out.rankings}

    matches: list[JobMatch] = []
    for i, job in enumerate(jobs):
        r = by_idx.get(i)
        if r is not None:
            matches.append(JobMatch(job=job, fit_score=r.fit_score,
                                    matched=r.matched, gaps=r.gaps, reason=r.reason))
        else:
            matches.append(JobMatch(job=job, fit_score=0, reason="未評分"))
    # 穩定排序：同分時以 url 決定先後，讓同一批職缺的顯示順序可重現（不隨並行/批次到達順序變動）。
    matches.sort(key=lambda m: (-m.fit_score, m.job.url or (m.job.title + m.job.company)))
    # 超出排序上限的職缺仍保留（附在後面、未評分），確保「不設限」顯示全部
    matches.extend(JobMatch(job=j, fit_score=0, reason="未評分") for j in overflow)
    return matches if top_k is None else matches[:top_k]
