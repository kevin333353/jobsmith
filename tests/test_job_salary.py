import pytest

from app.models import JobPosting
from app.sources.salary import filter_jobs_by_salary, monthly_salary_bounds, parse_salary_range


def test_parse_salary_range_normalizes_monthly_and_annual_ranges():
    monthly = parse_salary_range("月薪 NT$60,000–90,000")
    assert monthly.min_monthly == 60000
    assert monthly.max_monthly == 90000
    assert monthly.negotiable is False

    annual = parse_salary_range("年薪 TWD 1,200,000–1,800,000")
    assert annual.min_monthly == 100000
    assert annual.max_monthly == 150000

    open_annual = parse_salary_range("年薪 100萬以上")
    assert open_annual.min_monthly == pytest.approx(83333.33, abs=0.01)
    assert open_annual.max_monthly is None


def test_parse_salary_range_handles_k_and_negotiable_salary():
    compact = parse_salary_range("40K-60K")
    assert compact.min_monthly == 40000
    assert compact.max_monthly == 60000

    negotiable = parse_salary_range("待遇面議，依能力敘薪")
    assert negotiable.negotiable is True
    assert negotiable.min_monthly is None
    assert negotiable.max_monthly is None


def test_filter_jobs_by_salary_keeps_intersecting_ranges_and_optional_unknowns():
    jobs = [
        JobPosting(source="104", title="Too low", company="A", url="u1",
                   salary="月薪 NT$40,000–50,000"),
        JobPosting(source="104", title="Match", company="B", url="u2",
                   salary="月薪 NT$60,000–90,000"),
        JobPosting(source="cake", title="Too high", company="C", url="u3",
                   salary="年薪 TWD 1,500,000–2,100,000"),
        JobPosting(source="104", title="Negotiable", company="D", url="u4",
                   salary="面議"),
        JobPosting(source="yourator", title="Unknown", company="E", url="u5"),
    ]

    assert [j.title for j in filter_jobs_by_salary(
        jobs,
        min_monthly=60000,
        max_monthly=90000,
        include_unknown=True,
    )] == ["Match", "Negotiable", "Unknown"]

    assert [j.title for j in filter_jobs_by_salary(
        jobs,
        min_monthly=60000,
        max_monthly=90000,
        include_unknown=False,
    )] == ["Match"]


def test_monthly_salary_bounds_converts_annual_user_input():
    assert monthly_salary_bounds(1_200_000, 1_800_000, "annual") == (100000, 150000)
    assert monthly_salary_bounds(60_000, None, "monthly") == (60000, None)
