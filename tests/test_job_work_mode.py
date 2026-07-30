from app.models import JobPosting
from app.sources.work_mode import filter_jobs_by_work_mode, parse_work_modes


def _job(title: str, url: str, **kwargs) -> JobPosting:
    return JobPosting(source="test", title=title, company="C", url=url, **kwargs)


def test_job_posting_infers_strong_remote_and_hybrid_phrases():
    remote = _job("Backend Engineer", "r", snippet="本職缺 100% Remote，全程不用進辦公室")
    hybrid = _job("Product Manager", "h", raw_text="採混合式辦公，每週兩天居家工作")

    assert (remote.work_mode, remote.work_mode_origin) == ("remote", "inferred")
    assert (hybrid.work_mode, hybrid.work_mode_origin) == ("hybrid", "inferred")


def test_job_posting_does_not_promote_ambiguous_remote_text_to_fully_remote():
    job = _job("遠端工作工程師", "u", snippet="公司提供遠端工作制度")

    assert (job.work_mode, job.work_mode_origin) == ("unknown", "unknown")


def test_job_posting_ignores_remote_interview_only():
    job = _job("AI Engineer", "interview", snippet="一面採部分遠端面試，工作地點在台北")

    assert (job.work_mode, job.work_mode_origin) == ("unknown", "unknown")


def test_job_posting_recognizes_explicit_onsite_and_source_metadata():
    onsite = _job("Support Engineer", "o", snippet="本職缺不開放遠端，須每日進辦公室")
    source_remote = _job("Engineer", "s", work_mode="remote", work_mode_origin="source")

    assert onsite.work_mode == "onsite"
    assert onsite.work_mode_origin == "inferred"
    assert (source_remote.work_mode, source_remote.work_mode_origin) == ("remote", "source")


def test_work_mode_filter_is_strict_unless_inference_is_enabled():
    confirmed = _job("Confirmed", "c", work_mode="remote", work_mode_origin="source")
    inferred = _job("完全遠端 Backend", "i")
    hybrid = _job("Hybrid", "h", work_mode="hybrid", work_mode_origin="source")

    assert filter_jobs_by_work_mode([confirmed, inferred, hybrid], ["remote"]) == [confirmed]
    assert filter_jobs_by_work_mode(
        [confirmed, inferred, hybrid],
        ["remote"],
        include_inferred=True,
    ) == [confirmed, inferred]


def test_parse_work_modes_drops_unknowns_and_duplicates():
    assert parse_work_modes("remote, hybrid,REMOTE,onsite,garbage") == ["remote", "hybrid"]
    assert parse_work_modes("") == []
