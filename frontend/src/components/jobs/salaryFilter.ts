export type SalaryUnit = "monthly" | "annual"

export type SalaryFilterState = {
  unit: SalaryUnit
  min: string
  max: string
  includeUnknown: boolean
}

export function salaryFilterActive(state: SalaryFilterState): boolean {
  return Boolean(state.min.trim() || state.max.trim() || !state.includeUnknown)
}

export function appendSalaryFilter(form: FormData, state: SalaryFilterState): void {
  if (!salaryFilterActive(state)) return
  form.append("salary_unit", state.unit)
  if (state.min.trim()) form.append("min_salary", state.min.trim())
  if (state.max.trim()) form.append("max_salary", state.max.trim())
  form.append("include_unknown_salary", String(state.includeUnknown))
}
