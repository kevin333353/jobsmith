import pytest

from app.evals.harness import summarize, run_case
from app.evals.fixtures import GOLDEN
from app.models import CritiqueReport


def _crit(pass_, r, c, i):
    return CritiqueReport(resume_score=r, cover_letter_score=c, interview_score=i, overall_pass=pass_)


def test_summarize_computes_lift():
    rows = [
        {"name": "a", "off": _crit(False, 50, 60, 55), "on": _crit(True, 85, 88, 80)},
        {"name": "b", "off": _crit(False, 60, 60, 60), "on": _crit(True, 90, 80, 85)},
    ]
    s = summarize(rows)
    assert s["n"] == 2
    assert s["pass_rate_off"] == 0.0          # 兩案首輪都未過
    assert s["pass_rate_on"] == 100.0         # 反思後都過
    assert s["mean_on"] > s["mean_off"]
    assert s["mean_lift"] == round(s["mean_on"] - s["mean_off"], 1)
    assert s["pass_rate_lift"] == 100.0


def test_summarize_handles_empty_and_none():
    assert summarize([])["n"] == 0
    rows = [{"name": "x", "off": None, "on": _crit(True, 80, 80, 80)}]
    s = summarize(rows)
    assert s["mean_off"] == 0.0 and s["mean_on"] == 80.0


def test_golden_fixtures_are_well_formed():
    assert len(GOLDEN) >= 3
    for c in GOLDEN:
        assert c["jd_text"].strip()
        assert c["profile"].name and c["profile"].raw_text


@pytest.mark.live
def test_reflection_lifts_quality_live():
    # 真跑一個案例（claude_cli/anthropic），驗證反思開的最終分數 >= 反思關
    case = GOLDEN[0]
    off = run_case(case, max_revisions=0)
    on = run_case(case, max_revisions=3)
    assert off is not None and on is not None
    off_mean = (off.resume_score + off.cover_letter_score + off.interview_score) / 3
    on_mean = (on.resume_score + on.cover_letter_score + on.interview_score) / 3
    assert on_mean >= off_mean
