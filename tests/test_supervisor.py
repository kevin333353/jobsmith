from app.agents import supervisor as sup
from app.models import MatchReport, CritiqueReport, ParsedJob, Profile, SupervisorDecision
from tests.conftest import FakeLLM


def _job():
    return ParsedJob(title="AI 工程師", company="未來智能")


def _profile():
    return Profile(name="王", summary="後端", raw_text="…")


def _crit(overall_pass, **scores):
    base = dict(resume_score=80, cover_letter_score=80, interview_score=80)
    base.update(scores)
    return CritiqueReport(overall_pass=overall_pass, **base)


def test_match_uses_llm_decision(monkeypatch):
    # 即使分數低，LLM 判 proceed 就 proceed（證明是 LLM 動態調度，不是寫死門檻）
    monkeypatch.setattr(sup, "get_llm",
                        lambda tier: FakeLLM(SupervisorDecision(next_action="proceed", rationale="可補強")))
    d = sup.supervise_after_match(
        MatchReport(score=35, recommend_proceed=False, reason="r"), _job(), _profile())
    assert d.next_action == "proceed"


def test_match_fallback_on_llm_error(monkeypatch):
    def boom(tier):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(sup, "get_llm", boom)
    hi = sup.supervise_after_match(MatchReport(score=80, recommend_proceed=True, reason="r"), _job(), _profile())
    lo = sup.supervise_after_match(MatchReport(score=30, recommend_proceed=False, reason="r"), _job(), _profile())
    assert hi.next_action == "proceed"   # 門檻備援
    assert lo.next_action == "stop"


def test_critic_caps_at_max_without_calling_llm(monkeypatch):
    called = {"n": 0}

    def spy(tier):
        called["n"] += 1
        raise AssertionError("達上限不應呼叫 LLM")
    monkeypatch.setattr(sup, "get_llm", spy)
    d = sup.supervise_after_critic(_crit(False, resume_score=10), revision_count=3, max_revisions=3)
    assert d.next_action == "approve"
    assert called["n"] == 0


def test_critic_uses_llm_and_filters_bogus_docs(monkeypatch):
    monkeypatch.setattr(sup, "get_llm", lambda tier: FakeLLM(
        SupervisorDecision(next_action="revise", docs_to_revise=["resume", "bogus"])))
    d = sup.supervise_after_critic(_crit(False, resume_score=10), revision_count=0, max_revisions=3)
    assert d.next_action == "revise"
    assert d.docs_to_revise == ["resume"]   # 非法鍵被濾除


def test_critic_revise_with_empty_docs_falls_back(monkeypatch):
    # LLM 回 revise 但沒給有效文件（全被濾掉）→ 退回備援，避免空轉重寫迴圈
    monkeypatch.setattr(sup, "get_llm", lambda tier: FakeLLM(
        SupervisorDecision(next_action="revise", docs_to_revise=["bogus"])))
    # 評審整體已過 → 備援 approve（不該空轉）
    passed = sup.supervise_after_critic(_crit(True, resume_score=90), revision_count=0, max_revisions=3)
    assert passed.next_action == "approve"
    # 評審未過 → 備援用分數挑出該重寫的文件
    failed = sup.supervise_after_critic(_crit(False, resume_score=10), revision_count=0, max_revisions=3)
    assert failed.next_action == "revise" and "resume" in failed.docs_to_revise


def test_critic_fallback_uses_per_doc(monkeypatch):
    def boom(tier):
        raise RuntimeError("down")
    monkeypatch.setattr(sup, "get_llm", boom)
    crit = _crit(False, resume_score=10, cover_letter_score=90, interview_score=90)
    crit.per_doc = {"resume": ["量化成果"]}
    d = sup.supervise_after_critic(crit, revision_count=0, max_revisions=3)
    assert d.next_action == "revise"
    assert d.docs_to_revise == ["resume"]
