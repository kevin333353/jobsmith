import pytest

from app.evals.fixtures import GOLDEN
from app.evals.harness import run_case, summarize
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
def test_single_pass_quality_review_live():
    # 真跑一個案例（claude_cli/anthropic），驗證一次性品管可產出合法分數。
    case = GOLDEN[0]
    report = run_case(case)
    assert report is not None
    mean = (report.resume_score + report.cover_letter_score + report.interview_score) / 3
    assert 0 <= mean <= 100
