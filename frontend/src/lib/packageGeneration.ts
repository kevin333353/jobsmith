import type {
  GenerationOptions,
  JobMatch,
  MatchReport,
  PackageArtifact,
  ParsedJob,
  PipelineState,
} from "../types"

export const QUICK_GENERATION: GenerationOptions = {
  artifactTargets: ["resume"],
  companyResearch: false,
  qualityReview: false,
}

export const COMPLETE_APPLICATION: GenerationOptions = {
  artifactTargets: ["resume", "cover_letter"],
  companyResearch: false,
  qualityReview: false,
}

export const INTERVIEW_PREP: GenerationOptions = {
  artifactTargets: ["interview"],
  companyResearch: true,
  qualityReview: false,
}

const VALID_ARTIFACTS = new Set<PackageArtifact>(["resume", "cover_letter", "interview"])

export function normalizeGenerationOptions(
  input?: Partial<GenerationOptions> | null,
): GenerationOptions {
  const requested = input?.artifactTargets?.filter((item): item is PackageArtifact =>
    VALID_ARTIFACTS.has(item))
  const artifactTargets = [...new Set(requested?.length ? requested : QUICK_GENERATION.artifactTargets)]
  const usesCompanyContext = artifactTargets.some(
    (item) => item === "cover_letter" || item === "interview",
  )
  return {
    artifactTargets,
    companyResearch: Boolean(input?.companyResearch && usesCompanyContext),
    qualityReview: Boolean(input?.qualityReview),
  }
}

export function optionsFromPipelineState(state?: Partial<PipelineState> | null): GenerationOptions {
  const inferredTargets: PackageArtifact[] = []
  if (state?.tailored_resume) inferredTargets.push("resume")
  if (state?.cover_letter) inferredTargets.push("cover_letter")
  if (state?.interview_kit) inferredTargets.push("interview")
  return normalizeGenerationOptions({
    artifactTargets: state?.artifact_targets?.length
      ? state.artifact_targets
      : inferredTargets.length ? inferredTargets : undefined,
    companyResearch: state?.company_research_requested ?? Boolean(state?.company_brief),
    qualityReview: state?.quality_review ?? Boolean(state?.critique),
  })
}

export function generationPayload(options: GenerationOptions) {
  const normalized = normalizeGenerationOptions(options)
  return {
    artifact_targets: normalized.artifactTargets,
    company_research_requested: normalized.companyResearch,
    quality_review: normalized.qualityReview,
  }
}

export function estimateGenerationCalls(options: GenerationOptions, reuseSearchAnalysis = false) {
  const normalized = normalizeGenerationOptions(options)
  return (reuseSearchAnalysis ? 0 : 2)
    + normalized.artifactTargets.length
    + (normalized.companyResearch ? 1 : 0)
    + (normalized.qualityReview ? 1 : 0)
}

export function searchAnalysisPayload(jdText: string, match?: JobMatch | null): {
  parsed_job?: ParsedJob
  match_report?: MatchReport
} {
  if (!match) return {}
  const job = match.job
  const compactJd = jdText.trim().slice(0, 12_000)
  const parsed_job: ParsedJob = {
    title: job.title,
    company: job.company,
    location: job.location ?? null,
    responsibilities: compactJd ? [compactJd] : job.snippet ? [job.snippet] : [],
    required_skills: job.requirements || [],
    nice_to_have: [],
    min_years: job.min_years ?? null,
    tech_stack: [],
    language: /[\u3400-\u9fff]/.test(`${job.title}${job.snippet || ""}`) ? "zh" : "en",
    salary: job.salary ?? null,
  }
  const match_report: MatchReport = {
    score: Math.max(0, Math.min(100, match.fit_score)),
    matched: match.matched || [],
    gaps: match.gaps || [],
    suggestions: [],
    recommend_proceed: match.fit_score >= 60,
    reason: match.reason || "沿用職缺搜尋時的 AI 配對結果",
  }
  return { parsed_job, match_report }
}
