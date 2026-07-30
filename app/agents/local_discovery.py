"""First-class deterministic resume-to-job discovery.

This module performs query expansion and explainable ranking without an LLM,
embeddings, an API key, or a local generative model.
"""
from __future__ import annotations

from app.agents.role_taxonomy import infer_known_roles, matching_roles, query_variants
from app.agents.skill_lexicon import extract_skills
from app.models import JobMatch, JobPosting, Profile


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def _profile_blob(profile: Profile) -> str:
    return " ".join([
        profile.summary or "",
        " ".join(profile.skills or []),
        " ".join(profile.experiences or []),
        " ".join(profile.preferred_roles or []),
        profile.raw_text or "",
    ])


def derive_local_queries(profile: Profile, limit: int = 3) -> list[str]:
    """Derive stable Chinese/English job-board queries from a local Profile."""
    roles = _dedupe(list(profile.preferred_roles or []))
    if not roles:
        roles = infer_known_roles(_profile_blob(profile))

    candidates: list[str] = []
    variants = [query_variants(role) for role in roles[:3]]
    # Cover multiple plausible roles before spending slots on English aliases.
    candidates.extend(items[0] for items in variants if items)
    for items in variants:
        candidates.extend(items[1:2])

    skills = _dedupe(list(profile.skills or []))
    if roles and skills:
        candidates.append(f"{skills[0]} {roles[0]}")
    candidates.extend(skills[:3])

    return _dedupe(candidates)[:max(1, limit)] or ["職缺"]


def _job_blob(job: JobPosting) -> str:
    return " ".join([
        job.title or "",
        job.company or "",
        job.location or "",
        job.snippet or "",
        " ".join(str(requirement) for requirement in (job.requirements or [])),
        job.raw_text or "",
    ])


def _profile_skill_map(profile: Profile) -> dict[str, str]:
    canonical = extract_skills(_profile_blob(profile))
    out = {skill.casefold(): skill for skill in canonical}
    for skill in profile.skills or []:
        cleaned = " ".join(str(skill).split()).strip()
        if cleaned:
            out.setdefault(cleaned.casefold(), cleaned)
    return out


def _evidence_level(job: JobPosting) -> str:
    detailed_text = len((job.raw_text or "").strip())
    if len(job.requirements or []) >= 3 or detailed_text >= 300:
        return "high"
    if job.requirements or detailed_text >= 80 or len((job.snippet or "").strip()) >= 60:
        return "medium"
    return "low"


def _experience_score(profile: Profile, job: JobPosting) -> tuple[int | None, str | None]:
    if profile.years_experience is None or job.min_years is None:
        return None, None
    delta = profile.years_experience - job.min_years
    if delta >= 0:
        return 100, f"年資符合（履歷 {profile.years_experience:g} 年／要求 {job.min_years:g} 年）"
    if delta >= -1:
        return 70, f"年資接近（履歷 {profile.years_experience:g} 年／要求 {job.min_years:g} 年）"
    if delta >= -2:
        return 30, f"年資略有落差（履歷 {profile.years_experience:g} 年／要求 {job.min_years:g} 年）"
    return 0, f"年資可能不足（履歷 {profile.years_experience:g} 年／要求 {job.min_years:g} 年）"


def rank_jobs_locally(
    profile: Profile,
    jobs: list[JobPosting],
    top_k: int | None = None,
) -> list[JobMatch]:
    """Rank jobs with renormalized title/skill/experience components."""
    profile_roles = _dedupe(list(profile.preferred_roles or []))
    if not profile_roles:
        profile_roles = infer_known_roles(_profile_blob(profile))
    profile_skills = _profile_skill_map(profile)
    canonical_have = set(extract_skills(_profile_blob(profile)))

    matches: list[JobMatch] = []
    for job in jobs:
        blob = _job_blob(job)
        blob_folded = blob.casefold()
        job_skills = set(extract_skills(blob))
        role_hits = matching_roles(profile_roles, job.title)
        canonical_hits = sorted(canonical_have & job_skills)
        canonical_hit_keys = {skill.casefold() for skill in canonical_hits}

        raw_hits: list[str] = []
        for key, display in profile_skills.items():
            if key in canonical_hit_keys:
                continue
            if len(key) >= 2 and key in blob_folded:
                raw_hits.append(display)
        skill_hits = _dedupe([*canonical_hits, *raw_hits])
        gaps = sorted(job_skills - canonical_have)[:6]

        components: list[tuple[str, int, int]] = []
        if profile_roles:
            components.append(("title", 100 if role_hits else 0, 55))
        if job_skills:
            covered = min(len(job_skills), len(canonical_have & job_skills) + len(raw_hits))
            components.append(("skills", round(100 * covered / len(job_skills)), 35))
        elif raw_hits:
            denominator = max(1, min(len(profile_skills), 4))
            components.append(("skills", min(100, round(100 * len(raw_hits) / denominator)), 35))

        experience_score, experience_reason = _experience_score(profile, job)
        if experience_score is not None:
            components.append(("experience", experience_score, 10))

        if components:
            weighted = sum(score * weight for _, score, weight in components)
            total_weight = sum(weight for _, _, weight in components)
            fit_score = round(weighted / total_weight)
        else:
            fit_score = 20
        evidence_level = _evidence_level(job)
        # A title-only listing can be directionally relevant, but it cannot support
        # a "high fit" claim. Keep unknown fields neutral while capping confidence.
        if evidence_level == "low":
            fit_score = min(fit_score, 79)

        reasons: list[str] = []
        if role_hits:
            reasons.append(f"職稱方向相符：{'、'.join(role_hits[:2])}")
        if skill_hits:
            reasons.append(f"符合 {len(skill_hits)} 項技能")
        if gaps:
            reasons.append(f"職缺另提到 {'、'.join(gaps[:3])}")
        if experience_reason:
            reasons.append(experience_reason)
        if not reasons:
            reasons.append("目前只找到少量可比對訊號，建議查看原職缺確認")

        breakdown = {name: score for name, score, _ in components}
        matched = _dedupe([*(f"職稱：{role}" for role in role_hits), *skill_hits])
        matches.append(JobMatch(
            job=job,
            fit_score=max(0, min(100, fit_score)),
            matched=matched[:8],
            gaps=gaps,
            reason="；".join(reasons) + "。",
            ranking_mode="local",
            evidence_level=evidence_level,
            score_breakdown=breakdown,
        ))

    matches.sort(key=lambda match: (
        -match.fit_score,
        match.job.url or (match.job.title + match.job.company),
    ))
    return matches if top_k is None else matches[:top_k]
