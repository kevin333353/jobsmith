from app.models import Profile, JobPosting
from app.agents import job_search as mod
from tests.conftest import FakeLLM


def test_search_queries_tolerates_codex_shapes():
    # codex/gpt 可能把 queries 回 null 或單一字串，要收斂而非結構化解析失敗。
    assert mod.SearchQueries(queries=None).queries == []
    assert mod.SearchQueries(queries="AI 工程師").queries == ["AI 工程師"]


def test_rank_item_tolerates_null_lists():
    # matched/gaps 被回成 null、reason 被回成陣列時，要收斂而非報錯（否則整批排序被丟掉）。
    it = mod._RankItem(index=1, fit_score=80, matched=None, gaps=None, reason=["很合適", "技能吻合"])
    assert it.matched == [] and it.gaps == []
    assert it.reason == "很合適、技能吻合"
    assert mod._RankResult(rankings=None).rankings == []


def test_derive_queries(monkeypatch):
    canned = mod.SearchQueries(queries=["AI 工程師", "Python 後端"])
    monkeypatch.setattr(mod, "get_llm", lambda tier, **k: FakeLLM(canned))
    qs = mod.derive_queries(Profile(name="王", summary="後端", skills=["Python"], raw_text="r"))
    assert qs == ["AI 工程師", "Python 後端"]


def test_derive_queries_fallback_to_preferred_role(monkeypatch):
    canned = mod.SearchQueries(queries=[])
    monkeypatch.setattr(mod, "get_llm", lambda tier, **k: FakeLLM(canned))
    qs = mod.derive_queries(Profile(name="王", summary="x", preferred_roles=["資料工程師"], raw_text="r"))
    assert qs == ["資料工程師"]


def test_rank_jobs_sorts_desc_and_maps(monkeypatch):
    canned = mod._RankResult(rankings=[
        mod._RankItem(index=0, fit_score=40, reason="普通"),
        mod._RankItem(index=1, fit_score=90, matched=["Python"], reason="很合"),
    ])
    monkeypatch.setattr(mod, "get_llm", lambda tier, **k: FakeLLM(canned))
    jobs = [
        JobPosting(source="104", title="A", company="C1", url="u1"),
        JobPosting(source="yourator", title="B", company="C2", url="u2"),
    ]
    matches = mod.rank_jobs(Profile(name="王", summary="x", raw_text="r"), jobs)
    assert matches[0].job.title == "B" and matches[0].fit_score == 90
    assert matches[1].fit_score == 40
    assert "Python" in matches[0].matched


def test_rank_jobs_empty_returns_empty():
    assert mod.rank_jobs(Profile(name="x", summary="y", raw_text="z"), []) == []


def test_rank_jobs_stable_tiebreak_by_url(monkeypatch):
    # 同分時以 url 決定先後 → 顯示順序可重現，不隨輸入/批次到達順序變動。
    canned = mod._RankResult(rankings=[
        mod._RankItem(index=0, fit_score=50, reason="r"),
        mod._RankItem(index=1, fit_score=50, reason="r"),
    ])
    monkeypatch.setattr(mod, "get_llm", lambda tier, **k: FakeLLM(canned))
    jobs = [  # 輸入先 zzz 後 aaa；同分 → 排序後 aaa 應在前
        JobPosting(source="x", title="Z", company="c", url="https://x/zzz"),
        JobPosting(source="x", title="A", company="c", url="https://x/aaa"),
    ]
    out = mod.rank_jobs(Profile(name="王", summary="x", raw_text="r"), jobs)
    assert [m.job.url for m in out] == ["https://x/aaa", "https://x/zzz"]


def _ranker(n):
    return FakeLLM(mod._RankResult(rankings=[
        mod._RankItem(index=i, fit_score=100 - i, reason="r") for i in range(n)
    ]))


def _jobs(n):
    return [JobPosting(source="x", title=f"j{i}", company="c", url=f"u{i}") for i in range(n)]


def test_rank_jobs_no_cap(monkeypatch):
    monkeypatch.setattr(mod, "get_llm", lambda tier, **k: _ranker(20))
    out = mod.rank_jobs(Profile(name="王", summary="後端", raw_text="…"), _jobs(20), top_k=None)
    assert len(out) == 20                              # 不再截在 12
    assert out[0].fit_score >= out[-1].fit_score       # 已排序


def test_rank_jobs_overflow_kept(monkeypatch):
    n = mod._RANK_INPUT_MAX + 8
    monkeypatch.setattr(mod, "get_llm", lambda tier, **k: _ranker(mod._RANK_INPUT_MAX))
    out = mod.rank_jobs(Profile(name="王", summary="後端", raw_text="…"), _jobs(n), top_k=None)
    assert len(out) == n                               # 超出排序上限者仍保留


def test_rank_jobs_explicit_top_k(monkeypatch):
    monkeypatch.setattr(mod, "get_llm", lambda tier, **k: _ranker(20))
    out = mod.rank_jobs(Profile(name="王", summary="後端", raw_text="…"), _jobs(20), top_k=5)
    assert len(out) == 5
