import type { JobMatch, JobPosting } from "../../types"
import { salaryMatchesFilter, type SalaryUnit } from "./salaryFilter.ts"

export type ResultWorkMode = NonNullable<JobPosting["work_mode"]>
export type ResultWorkModeOrigin = NonNullable<JobPosting["work_mode_origin"]>

export type ResultRefinementState = {
  query: string
  location: string
  sources: string[]
  workModes: ResultWorkMode[]
  workModeOrigins: ResultWorkModeOrigin[]
  minFit: number
  maxExperienceYears: string
  salaryUnit: SalaryUnit
  minSalary: string
  maxSalary: string
  includeUnknownSalary: boolean
}

export const RESULT_WORK_MODE_OPTIONS: ReadonlyArray<{
  value: ResultWorkMode
  label: string
}> = [
  { value: "remote", label: "完全遠端" },
  { value: "hybrid", label: "部分／混合遠端" },
  { value: "onsite", label: "現場工作" },
  { value: "unknown", label: "未標示" },
]

export const RESULT_WORK_MODE_ORIGIN_OPTIONS: ReadonlyArray<{
  value: ResultWorkModeOrigin
  label: string
}> = [
  { value: "source", label: "來源明確標示" },
  { value: "inferred", label: "JD 文字推測" },
  { value: "unknown", label: "未標示" },
]

const WORK_MODES = new Set<ResultWorkMode>(RESULT_WORK_MODE_OPTIONS.map((option) => option.value))
const WORK_MODE_ORIGINS = new Set<ResultWorkModeOrigin>(
  RESULT_WORK_MODE_ORIGIN_OPTIONS.map((option) => option.value),
)
const FIT_VALUES = new Set([0, 60, 80])
const EXPERIENCE_VALUES = new Set(["", "0", "1", "2", "3", "5"])

export function createEmptyResultRefinement(): ResultRefinementState {
  return {
    query: "",
    location: "",
    sources: [],
    workModes: [],
    workModeOrigins: [],
    minFit: 0,
    maxExperienceYears: "",
    salaryUnit: "monthly",
    minSalary: "",
    maxSalary: "",
    includeUnknownSalary: true,
  }
}

export function normalizeResultRefinement(value: unknown): ResultRefinementState {
  const defaults = createEmptyResultRefinement()
  if (!value || typeof value !== "object") return defaults
  const raw = value as Record<string, unknown>
  return {
    query: stringValue(raw.query),
    location: stringValue(raw.location),
    sources: uniqueStrings(raw.sources),
    workModes: uniqueStrings(raw.workModes)
      .filter((item): item is ResultWorkMode => WORK_MODES.has(item as ResultWorkMode)),
    workModeOrigins: uniqueStrings(raw.workModeOrigins)
      .filter((item): item is ResultWorkModeOrigin => (
        WORK_MODE_ORIGINS.has(item as ResultWorkModeOrigin)
      )),
    minFit: typeof raw.minFit === "number" && FIT_VALUES.has(raw.minFit) ? raw.minFit : 0,
    maxExperienceYears: (
      typeof raw.maxExperienceYears === "string"
      && EXPERIENCE_VALUES.has(raw.maxExperienceYears)
    ) ? raw.maxExperienceYears : "",
    salaryUnit: raw.salaryUnit === "annual" ? "annual" : "monthly",
    minSalary: stringValue(raw.minSalary),
    maxSalary: stringValue(raw.maxSalary),
    includeUnknownSalary: typeof raw.includeUnknownSalary === "boolean"
      ? raw.includeUnknownSalary
      : true,
  }
}

export function resultRefinementActive(state: ResultRefinementState): boolean {
  return Boolean(
    state.query.trim()
    || state.location.trim()
    || state.sources.length
    || state.workModes.length
    || state.workModeOrigins.length
    || state.minFit
    || state.maxExperienceYears
    || state.minSalary.trim()
    || state.maxSalary.trim()
    || !state.includeUnknownSalary,
  )
}

export function filterJobMatches(
  matches: JobMatch[],
  state: ResultRefinementState,
): JobMatch[] {
  const query = normalizedText(state.query)
  const location = normalizedText(state.location)
  const maxYears = state.maxExperienceYears === ""
    ? null
    : Number(state.maxExperienceYears)

  return matches.filter((match) => {
    const job = match.job
    if (match.fit_score < state.minFit) return false
    if (state.sources.length && !state.sources.includes(job.source)) return false

    const workMode = job.work_mode || "unknown"
    if (state.workModes.length && !state.workModes.includes(workMode)) return false
    const origin = job.work_mode_origin || "unknown"
    if (state.workModeOrigins.length && !state.workModeOrigins.includes(origin)) return false

    if (query && !jobSearchText(match).includes(query)) return false
    if (location && !normalizedText(job.location || "").includes(location)) return false
    if (
      maxYears !== null
      && typeof job.min_years === "number"
      && job.min_years > maxYears
    ) return false

    return salaryMatchesFilter(job.salary, {
      unit: state.salaryUnit,
      min: state.minSalary,
      max: state.maxSalary,
      includeUnknown: state.includeUnknownSalary,
    })
  })
}

function jobSearchText(match: JobMatch): string {
  const job = match.job
  return normalizedText([
    job.title,
    job.company,
    job.location || "",
    job.snippet || "",
    ...job.requirements,
    match.reason,
    ...match.matched,
    ...match.gaps,
  ].join(" "))
}

function normalizedText(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase()
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function uniqueStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return [...new Set(value.filter((item): item is string => (
    typeof item === "string" && item.trim().length > 0
  )))]
}
