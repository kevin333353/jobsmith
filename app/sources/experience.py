"""Extract coarse minimum experience requirements from job listing text."""
from __future__ import annotations

import re

_NO_EXPERIENCE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"不限(?:工作)?(?:年資|經驗)",
        r"(?:年資|經驗)(?:不拘|不限)",
        r"無(?:相關|工作)?經驗(?:可|亦可)?",
        r"歡迎新鮮人",
        r"fresh\s+graduates?\s+(?:are\s+)?welcome",
        r"no\s+experience\s+(?:required|needed)",
    )
]

_RANGE_RE = re.compile(
    r"(?P<min>\d+(?:\.\d+)?)\s*(?:-|~|–|至|到)\s*(?P<max>\d+(?:\.\d+)?)\s*(?:年|years?|yrs?)",
    re.IGNORECASE,
)
_PLUS_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*\+\s*(?:年|years?|yrs?)", re.IGNORECASE)
_MINIMUM_RE = re.compile(
    r"(?:(?:至少|最少|最低|需|需要|具備|擁有|具有|at\s+least|required)\s*)?"
    r"(?P<num>\d+(?:\.\d+)?)\s*(?:年|years?|yrs?)\s*(?:以上|經驗|experience)?",
    re.IGNORECASE,
)


def parse_experience_requirement(*parts: str | None) -> tuple[float | None, str | None]:
    text = " ".join(str(part) for part in parts if part).strip()
    if not text:
        return None, None

    for pattern in _NO_EXPERIENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            return 0.0, _clean_entry_level_match(match.group(0))

    for pattern, group in ((_RANGE_RE, "min"), (_PLUS_RE, "num"), (_MINIMUM_RE, "num")):
        match = pattern.search(text)
        if match:
            return float(match.group(group)), _clean_match(match.group(0))
    return None, None


def _clean_match(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" ，,。；;")
    text = re.sub(r"^(?:需要|需|具備|擁有|具有|required)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*(?:經驗|experience|exp)$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _clean_entry_level_match(text: str) -> str:
    text = _clean_match(text)
    if "不限" in text and "年資" in text:
        return "不限年資"
    if "不限" in text and "經驗" in text:
        return "不限經驗"
    if "無" in text and "經驗" in text:
        return "無經驗"
    return text
