import type { SalaryUnit } from "../components/jobs/salaryFilter"
import type { WorkModeFilter } from "./workMode"

export interface SearchScopeState {
  regions: string[]
  workModes: WorkModeFilter[]
  includeInferredWorkMode: boolean
  maxExperienceYears: string
  salaryUnit: SalaryUnit
  minSalary: string
  maxSalary: string
  includeUnknownSalary: boolean
  companies: string[]
  pages: number
}

export interface SearchScopeDescription {
  activeCount: number
  items: string[]
}

const WORK_MODE_LABELS: Record<WorkModeFilter, string> = {
  remote: "完全遠端",
  hybrid: "混合遠端",
}

export function describeSearchScope(state: SearchScopeState): SearchScopeDescription {
  const items: string[] = []
  let activeCount = 0

  if (state.regions.length) {
    activeCount += 1
    items.push(state.regions.length === 1 ? state.regions[0] : `${state.regions.length} 個地區`)
  } else {
    items.push("全台")
  }

  if (state.workModes.length) {
    activeCount += 1
    const label = state.workModes.map((mode) => WORK_MODE_LABELS[mode]).join("＋")
    items.push(state.includeInferredWorkMode ? `${label}（含推測）` : label)
  } else {
    items.push("不限工作型態")
  }

  if (state.minSalary.trim() || state.maxSalary.trim() || !state.includeUnknownSalary) {
    activeCount += 1
    const unit = state.salaryUnit === "annual" ? "年薪" : "月薪"
    const range = [state.minSalary.trim(), state.maxSalary.trim()].filter(Boolean).join("–")
    items.push(range ? `${unit} ${range}` : "只看有薪資職缺")
  }

  if (state.maxExperienceYears.trim()) {
    activeCount += 1
    items.push(`要求年資 ≤ ${state.maxExperienceYears} 年`)
  }

  if (state.companies.length) {
    activeCount += 1
    items.push(`${state.companies.length} 間指定公司`)
  }

  if (state.pages !== 2) {
    activeCount += 1
    items.push(`每站 ${state.pages} 頁`)
  }

  return { activeCount, items }
}
