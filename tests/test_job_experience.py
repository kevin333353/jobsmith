from app.models import JobPosting
from app.sources.experience import parse_experience_requirement


def test_parse_experience_requirement_extracts_chinese_minimums():
    assert parse_experience_requirement("Python 後端，3年以上經驗") == (3.0, "3年以上")
    assert parse_experience_requirement("至少 2 年 API 開發經驗") == (2.0, "至少 2 年")
    assert parse_experience_requirement("1-3 年相關經驗") == (1.0, "1-3 年")


def test_parse_experience_requirement_handles_entry_level_jobs():
    assert parse_experience_requirement("不限年資，歡迎新鮮人") == (0.0, "不限年資")
    assert parse_experience_requirement("無經驗可，有 mentor 帶") == (0.0, "無經驗")


def test_parse_experience_requirement_extracts_english_minimums():
    assert parse_experience_requirement("3+ years of backend experience") == (3.0, "3+ years")
    assert parse_experience_requirement("5 years experience with Python") == (5.0, "5 years")


def test_job_posting_infers_experience_fields_from_search_text():
    job = JobPosting(
        source="104",
        title="Backend Engineer",
        company="C",
        url="u",
        snippet="需要 4 年以上 Python 後端經驗",
    )

    assert job.min_years == 4.0
    assert job.experience_text == "4 年以上"
