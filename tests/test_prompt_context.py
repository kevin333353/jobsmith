import json

from app.agents.prompt_context import profile_prompt_json, relevant_resume_evidence
from app.models import ParsedJob, Profile


def _job():
    return ParsedJob(
        title="Python 後端工程師",
        company="測試公司",
        required_skills=["Python", "FastAPI"],
        tech_stack=["PostgreSQL"],
    )


def test_compact_profile_excludes_repeated_raw_text():
    profile = Profile(
        name="王",
        summary="後端工程師",
        skills=["Python"],
        experiences=["開發 API"],
        raw_text="THIS_WHOLE_RAW_RESUME_SHOULD_NOT_REPEAT",
    )
    data = json.loads(profile_prompt_json(profile))

    assert "raw_text" not in data
    assert "parse_degraded" not in data
    assert "THIS_WHOLE_RAW_RESUME_SHOULD_NOT_REPEAT" not in json.dumps(data)


def test_resume_evidence_prefers_job_terms_and_quantified_results():
    raw = "\n".join([
        "個人興趣：攝影與旅行",
        "使用 Python 與 FastAPI 建立訂單 API，延遲降低 35%",
        "維護 PostgreSQL 並帶領 3 人完成資料搬遷",
        "社團活動：羽球社",
    ])
    evidence = relevant_resume_evidence(raw, _job(), max_chars=120)

    assert "Python" in evidence
    assert "35%" in evidence
    assert len(evidence) <= 120
    assert "攝影與旅行" not in evidence


def test_resume_prompt_adds_bounded_relevant_evidence():
    profile = Profile(
        name="王",
        summary="後端",
        skills=["Python"],
        experiences=["API 經驗"],
        raw_text="Python FastAPI 專案吞吐提升 40%\n完全無關內容",
    )
    data = json.loads(profile_prompt_json(profile, job=_job(), include_relevant_raw=True))

    assert "raw_text" not in data
    assert "Python FastAPI" in data["relevant_resume_evidence"]


def test_sparse_profile_keeps_small_raw_fallback():
    profile = Profile(name="王", summary="", raw_text="原始履歷內容")
    data = json.loads(profile_prompt_json(profile))
    assert data["resume_excerpt"] == "原始履歷內容"
