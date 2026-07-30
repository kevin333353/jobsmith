from app.agents import company_jobs as cj
from app.models import JobPosting, JobPostingList, SearchResult


def test_merges_boards_and_careers(monkeypatch):
    monkeypatch.setattr(cj, "search_all", lambda kw, limit=15: [SearchResult(source="104", jobs=[
        JobPosting(source="104", title="AI 工程師", company="未來智能", url="u1"),
        JobPosting(source="104", title="PM", company="別家公司", url="u2"),
    ])])
    monkeypatch.setattr(cj, "research_structured", lambda *a, **k: JobPostingList(items=[
        JobPosting(source="careers", title="ML Engineer", company="未來智能",
                   url="https://futai.com/jobs/ml"),
    ]))
    out = cj.find_company_jobs("未來智能")
    titles = {j.title for j in out}
    assert "AI 工程師" in titles and "ML Engineer" in titles
    assert "PM" not in titles                       # 公司不符被濾掉


def test_careers_skipped_when_unsupported(monkeypatch):
    monkeypatch.setattr(cj, "search_all", lambda kw, limit=15: [SearchResult(source="104", jobs=[
        JobPosting(source="104", title="AI", company="未來智能", url="u1"),
    ])])
    monkeypatch.setattr(cj, "research_structured", lambda *a, **k: None)  # 非 CLI 後端
    out = cj.find_company_jobs("未來智能")
    assert len(out) == 1 and out[0].source == "104"


def test_dedupes_same_url(monkeypatch):
    monkeypatch.setattr(cj, "search_all", lambda kw, limit=15: [SearchResult(source="104", jobs=[
        JobPosting(source="104", title="AI", company="未來智能", url="https://x/1"),
    ])])
    monkeypatch.setattr(cj, "research_structured", lambda *a, **k: JobPostingList(items=[
        JobPosting(source="careers", title="AI", company="未來智能", url="https://x/1"),
    ]))
    assert len(cj.find_company_jobs("未來智能")) == 1   # 同 url 去重


def test_remote_options_are_forwarded_to_board_search(monkeypatch):
    captured = {}

    def fake_search(kw, limit=15, work_modes=None, include_inferred=False):
        captured["work_modes"] = work_modes
        captured["include_inferred"] = include_inferred
        return []

    monkeypatch.setattr(cj, "search_all", fake_search)
    monkeypatch.setattr(cj, "research_structured", lambda *a, **k: None)

    cj.find_company_jobs("未來智能", work_modes=["remote"], include_inferred=True)

    assert captured == {"work_modes": ["remote"], "include_inferred": True}


def test_no_ai_mode_skips_careers_research(monkeypatch):
    monkeypatch.setattr(cj, "search_all", lambda kw, limit=15: [SearchResult(source="104", jobs=[
        JobPosting(source="104", title="產品經理", company="未來智能", url="u1"),
    ])])

    def fail_research(*args, **kwargs):
        raise AssertionError("no-AI company search must not call research_structured")

    monkeypatch.setattr(cj, "research_structured", fail_research)

    out = cj.find_company_jobs("未來智能", include_research=False)

    assert [job.url for job in out] == ["u1"]
