export const EXPERIENCE_FILTER_OPTIONS = [
  { value: "", label: "不篩年資" },
  { value: "0", label: "只看新鮮人 / 未標示年資" },
  { value: "1", label: "排除要求超過 1 年" },
  { value: "2", label: "排除要求超過 2 年" },
  { value: "3", label: "排除要求超過 3 年" },
  { value: "5", label: "排除要求超過 5 年" },
]

export function jobExperienceLabel(job: { min_years?: number | null; experience_text?: string | null }): string {
  if (typeof job.min_years === "number" && job.min_years <= 0) return job.experience_text || "不限年資"
  if (job.experience_text) return `年資 ${job.experience_text}`
  if (typeof job.min_years !== "number") return ""
  return `年資 ${formatYears(job.min_years)} 年以上`
}

function formatYears(years: number): string {
  return Number.isInteger(years) ? String(years) : String(years).replace(/\.0$/, "")
}
