import type { UserProfile } from "../types"

export type JobSearchMode = "local" | "ai"

export const DEFAULT_JOB_SEARCH_MODE: JobSearchMode = "local"
export const MAX_TARGET_ROLES = 3

export function normalizeJobSearchMode(value: unknown): JobSearchMode {
  return value === "ai" ? "ai" : DEFAULT_JOB_SEARCH_MODE
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => typeof item === "string" ? item.trim() : "")
    .filter(Boolean)
}

export function normalizeTargetRoles(
  value: unknown,
  limit: number = MAX_TARGET_ROLES,
): string[] {
  const source = Array.isArray(value) ? value : typeof value === "string" ? [value] : []
  const seen = new Set<string>()
  const roles: string[] = []
  for (const item of source) {
    if (typeof item !== "string") continue
    for (const part of item.split(/[,，、\n]/)) {
      const role = part.replace(/\s+/g, " ").trim()
      const key = role.toLocaleLowerCase()
      if (!role || role.length > 80 || seen.has(key)) continue
      seen.add(key)
      roles.push(role)
      if (roles.length >= limit) return roles
    }
  }
  return roles
}

export function profileTargetRoles(profile?: UserProfile | null): string[] {
  if (!profile || typeof profile !== "object") return []
  const record = profile as Record<string, unknown>
  return normalizeTargetRoles(record.preferred_roles)
    .filter((role) => role !== "一般職缺" && role !== "職缺")
}

export interface ProfileRecognition {
  name: string
  summary: string
  roles: string[]
  skills: string[]
  yearsExperience: number | null
}

export function profileRecognition(profile?: UserProfile | null): ProfileRecognition | null {
  if (!profile || typeof profile !== "object") return null
  const record = profile as Record<string, unknown>
  const rawYears = record.years_experience
  const numericYears = typeof rawYears === "number"
    ? rawYears
    : typeof rawYears === "string" && rawYears.trim() ? Number(rawYears) : Number.NaN
  return {
    name: typeof record.name === "string" ? record.name.trim() : "",
    summary: typeof record.summary === "string" ? record.summary.trim() : "",
    roles: profileTargetRoles(profile),
    skills: stringList(record.skills),
    yearsExperience: Number.isFinite(numericYears) ? numericYears : null,
  }
}
