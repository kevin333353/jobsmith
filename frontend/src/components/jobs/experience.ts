export function jobExperienceLabel(job: { min_years?: number | null; experience_text?: string | null }): string {
  if (typeof job.min_years === "number" && job.min_years <= 0) return job.experience_text || "不限年資"
  if (job.experience_text) return `年資 ${job.experience_text}`
  if (typeof job.min_years !== "number") return ""
  return `年資 ${formatYears(job.min_years)} 年以上`
}

function formatYears(years: number): string {
  return Number.isInteger(years) ? String(years) : String(years).replace(/\.0$/, "")
}
