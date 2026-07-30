import type { JobPosting } from "../types"

export type WorkModeFilter = "remote" | "hybrid"

export const WORK_MODE_OPTIONS: ReadonlyArray<{ value: WorkModeFilter; label: string }> = [
  { value: "remote", label: "完全遠端" },
  { value: "hybrid", label: "部分／混合遠端" },
]

export function normalizeWorkModeFilters(value: unknown): WorkModeFilter[] {
  if (!Array.isArray(value)) return []
  const out: WorkModeFilter[] = []
  for (const item of value) {
    if ((item === "remote" || item === "hybrid") && !out.includes(item)) out.push(item)
  }
  return out
}

export function appendWorkModeFilter(
  form: FormData,
  modes: WorkModeFilter[],
  includeInferred: boolean,
): void {
  if (!modes.length) return
  form.append("work_mode", modes.join(","))
  form.append("include_inferred_work_mode", String(includeInferred))
}

type BadgeTone = "emerald" | "amber" | "slate"

export function jobWorkModeBadge(
  job: Pick<JobPosting, "work_mode" | "work_mode_origin">,
): { label: string; tone: BadgeTone } | null {
  const mode = job.work_mode
  if (!mode || mode === "unknown") return null
  const modeLabel = mode === "remote"
    ? "完全遠端"
    : mode === "hybrid"
      ? "部分／混合遠端"
      : "現場工作"
  if (job.work_mode_origin === "source") {
    return { label: `來源標示：${modeLabel}`, tone: mode === "onsite" ? "slate" : "emerald" }
  }
  if (job.work_mode_origin === "inferred") {
    return { label: `JD 文字推測：${modeLabel}`, tone: "amber" }
  }
  return null
}
