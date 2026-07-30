import json
from pathlib import Path

from app.agents.local_discovery import derive_local_queries, rank_jobs_locally
from app.agents.resume_eval import structure_profile_local
from app.models import JobPosting, Profile

SYNTHETIC_OCCUPATION_CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "synthetic_occupation_resumes.json").read_text(
        encoding="utf-8",
    ),
)


def test_local_queries_expand_non_technical_role_without_llm():
    profile = Profile(
        name="王小明",
        summary="產品經理",
        preferred_roles=["產品經理"],
        skills=["user research", "roadmap"],
    )

    queries = derive_local_queries(profile)

    assert queries[0] == "產品經理"
    assert "Product Manager" in queries
    assert len(queries) <= 3


def test_local_rank_is_explainable_and_separates_evidence_level():
    profile = Profile(
        name="王小明",
        summary="產品經理",
        preferred_roles=["產品經理"],
        skills=["product management", "user research"],
        years_experience=4,
    )
    jobs = [
        JobPosting(
            source="cake",
            title="Product Manager",
            company="A",
            url="https://example.com/product",
            requirements=["product management", "user research", "Figma"],
            min_years=3,
        ),
        JobPosting(
            source="104",
            title="Backend Engineer",
            company="B",
            url="https://example.com/backend",
            snippet="Python FastAPI",
            min_years=3,
        ),
    ]

    ranked = rank_jobs_locally(profile, jobs)

    assert ranked[0].job.title == "Product Manager"
    assert ranked[0].fit_score > ranked[1].fit_score
    assert ranked[0].ranking_mode == "local"
    assert ranked[0].evidence_level == "high"
    assert "Figma" in ranked[0].gaps
    assert ranked[0].score_breakdown["title"] == 100
    assert "職稱方向相符" in ranked[0].reason


def test_local_rank_does_not_treat_unknown_job_fields_as_candidate_gaps():
    profile = Profile(
        name="王小明",
        summary="客戶成功",
        preferred_roles=["客戶成功"],
        skills=["CRM"],
    )
    job = JobPosting(
        source="linkedin",
        title="Customer Success Manager",
        company="A",
        url="https://example.com/cs",
    )

    match = rank_jobs_locally(profile, [job])[0]

    assert match.fit_score == 79
    assert match.evidence_level == "low"
    assert match.gaps == []


def test_unknown_user_confirmed_role_is_searched_and_ranked_verbatim():
    profile = Profile(
        name="合成候選人",
        summary="寵物美容工作經驗",
        preferred_roles=["寵物美容師"],
        skills=["寵物洗護"],
    )
    jobs = [
        JobPosting(
            source="104",
            title="寵物美容師",
            company="A",
            url="https://example.com/pet-groomer",
            snippet="寵物洗護與造型",
        ),
        JobPosting(
            source="104",
            title="行政專員",
            company="B",
            url="https://example.com/admin",
            snippet="文件整理",
        ),
    ]

    assert derive_local_queries(profile)[0] == "寵物美容師"
    ranked = rank_jobs_locally(profile, jobs)
    assert ranked[0].job.title == "寵物美容師"
    assert ranked[0].fit_score > ranked[1].fit_score


def test_synthetic_resume_matrix_covers_broad_non_technical_occupations():
    assert len(SYNTHETIC_OCCUPATION_CASES) >= 30

    for case in SYNTHETIC_OCCUPATION_CASES:
        profile = structure_profile_local(case["resume"])
        queries = derive_local_queries(profile)
        matching = JobPosting(
            source="104",
            title=case["job_title"],
            company="合成測試公司",
            url=f"https://example.com/{case['id']}",
            requirements=[case["expected_skill"]],
            raw_text=f"{case['job_title']} {case['expected_skill']}",
        )
        unrelated = JobPosting(
            source="104",
            title="完全不相關職缺",
            company="合成測試公司",
            url=f"https://example.com/{case['id']}-unrelated",
            requirements=["完全不同技能"],
        )
        ranked = rank_jobs_locally(profile, [unrelated, matching])

        assert profile.preferred_roles[0] == case["expected_role"], case["id"]
        assert queries[0] == case["expected_role"], case["id"]
        assert case["expected_skill"] in profile.skills, case["id"]
        assert ranked[0].job.title == case["job_title"], case["id"]
