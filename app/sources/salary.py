"""Normalize coarse salary ranges for search filtering."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SalaryRange:
    min_monthly: float | None = None
    max_monthly: float | None = None
    negotiable: bool = False

    @property
    def has_amount(self) -> bool:
        return self.min_monthly is not None or self.max_monthly is not None


_NEGOTIABLE_RE = re.compile(r"(面議|另議|依能力|依經驗|negotiable)", re.IGNORECASE)
_ANNUAL_RE = re.compile(r"(年薪|per[_\s-]?year|annual|annually|/year)", re.IGNORECASE)
_MONTHLY_RE = re.compile(r"(月薪|per[_\s-]?month|monthly|/month|/mo)", re.IGNORECASE)
_UNSUPPORTED_PERIOD_RE = re.compile(r"(時薪|日薪|hourly|per[_\s-]?hour|daily|per[_\s-]?day)", re.IGNORECASE)
_OPEN_MIN_RE = re.compile(r"(以上|起|up|above|minimum)", re.IGNORECASE)
_OPEN_MAX_RE = re.compile(r"(以下|以內|under|maximum|max)", re.IGNORECASE)
_AMOUNT = r"(?:NT\$|NTD|TWD|新台幣|台幣|\$)?\s*(?P<{name}>\d[\d,]*(?:\.\d+)?)\s*(?P<{unit}>萬|万|[kK])?"
_RANGE_RE = re.compile(
    _AMOUNT.format(name="lo", unit="lo_unit")
    + r"\s*(?:-|~|–|—|至|到)\s*"
    + _AMOUNT.format(name="hi", unit="hi_unit"),
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(_AMOUNT.format(name="num", unit="num_unit"), re.IGNORECASE)


def parse_salary_range(text: str | None) -> SalaryRange:
    raw = (text or "").strip()
    if not raw:
        return SalaryRange()

    period = _period(raw)
    if period is None:
        return SalaryRange(negotiable=bool(_NEGOTIABLE_RE.search(raw)))

    range_match = _RANGE_RE.search(raw)
    if range_match:
        low = _amount(range_match.group("lo"), range_match.group("lo_unit"))
        high = _amount(range_match.group("hi"), range_match.group("hi_unit"))
        if high < low:
            low, high = high, low
        return SalaryRange(
            min_monthly=_to_monthly(low, period),
            max_monthly=_to_monthly(high, period),
        )

    single_match = _SINGLE_RE.search(raw)
    if not single_match:
        return SalaryRange(negotiable=bool(_NEGOTIABLE_RE.search(raw)))

    value = _to_monthly(_amount(single_match.group("num"), single_match.group("num_unit")), period)
    if _OPEN_MAX_RE.search(raw):
        return SalaryRange(max_monthly=value)
    if _OPEN_MIN_RE.search(raw):
        return SalaryRange(min_monthly=value)
    return SalaryRange(min_monthly=value, max_monthly=value)


def monthly_salary_bounds(
    min_salary: float | int | str | None,
    max_salary: float | int | str | None,
    unit: str,
) -> tuple[float | None, float | None]:
    factor = 12.0 if (unit or "").lower() == "annual" else 1.0
    low = _input_amount(min_salary, factor)
    high = _input_amount(max_salary, factor)
    if low is not None and high is not None and high < low:
        low, high = high, low
    return low, high


def filter_jobs_by_salary(
    jobs: Iterable,
    *,
    min_monthly: float | None,
    max_monthly: float | None,
    include_unknown: bool,
) -> list:
    if min_monthly is None and max_monthly is None and include_unknown:
        return list(jobs)

    wanted_min = min_monthly if min_monthly is not None else 0.0
    wanted_max = max_monthly if max_monthly is not None else math.inf
    kept = []
    for job in jobs:
        salary = parse_salary_range(getattr(job, "salary", None))
        if not salary.has_amount:
            if include_unknown:
                kept.append(job)
            continue
        job_min = salary.min_monthly if salary.min_monthly is not None else 0.0
        job_max = salary.max_monthly if salary.max_monthly is not None else math.inf
        if job_max >= wanted_min and wanted_max >= job_min:
            kept.append(job)
    return kept


def _period(text: str) -> str | None:
    if _ANNUAL_RE.search(text):
        return "annual"
    if _MONTHLY_RE.search(text):
        return "monthly"
    if _UNSUPPORTED_PERIOD_RE.search(text):
        return None
    return "monthly"


def _amount(raw: str, unit: str | None) -> float:
    value = float(raw.replace(",", ""))
    if unit in {"萬", "万"}:
        return value * 10000
    if unit and unit.lower() == "k":
        return value * 1000
    return value


def _to_monthly(value: float, period: str) -> float:
    monthly = value / 12.0 if period == "annual" else value
    return round(monthly, 2)


def _input_amount(value: float | int | str | None, factor: float) -> float | None:
    if value is None or value == "":
        return None
    try:
        amount = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if amount < 0:
        amount = 0.0
    return round(amount / factor, 2)
