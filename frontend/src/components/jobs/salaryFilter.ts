export type SalaryUnit = "monthly" | "annual"

export type SalaryFilterState = {
  unit: SalaryUnit
  min: string
  max: string
  includeUnknown: boolean
}

export type SalaryRange = {
  minMonthly: number | null
  maxMonthly: number | null
  negotiable: boolean
}

const NEGOTIABLE_RE = /(面議|另議|依能力|依經驗|negotiable)/i
const ANNUAL_RE = /(年薪|per[_\s-]?year|annual|annually|\/year)/i
const MONTHLY_RE = /(月薪|per[_\s-]?month|monthly|\/month|\/mo)/i
const UNSUPPORTED_PERIOD_RE = /(時薪|日薪|hourly|per[_\s-]?hour|daily|per[_\s-]?day)/i
const OPEN_MIN_RE = /(以上|起|up|above|minimum)/i
const OPEN_MAX_RE = /(以下|以內|under|maximum|max)/i
const CURRENCY = String.raw`(?:NT\$|NTD|TWD|新台幣|台幣|\$)?`
const NUMBER = String.raw`(\d[\d,]*(?:\.\d+)?)`
const UNIT = String.raw`(萬|万|[kK])?`
const AMOUNT = `${CURRENCY}\\s*${NUMBER}\\s*${UNIT}`
const RANGE_RE = new RegExp(`${AMOUNT}\\s*(?:-|~|–|—|至|到)\\s*${AMOUNT}`, "i")
const SINGLE_RE = new RegExp(AMOUNT, "i")

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

export function parseSalaryRange(text: string | null | undefined): SalaryRange {
  const raw = (text || "").trim()
  if (!raw) return emptySalaryRange()

  const period = salaryPeriod(raw)
  if (!period) return { ...emptySalaryRange(), negotiable: NEGOTIABLE_RE.test(raw) }

  const rangeMatch = RANGE_RE.exec(raw)
  if (rangeMatch) {
    let low = salaryAmount(rangeMatch[1], rangeMatch[2])
    let high = salaryAmount(rangeMatch[3], rangeMatch[4])
    if (high < low) [low, high] = [high, low]
    return {
      minMonthly: toMonthly(low, period),
      maxMonthly: toMonthly(high, period),
      negotiable: false,
    }
  }

  const singleMatch = SINGLE_RE.exec(raw)
  if (!singleMatch) return { ...emptySalaryRange(), negotiable: NEGOTIABLE_RE.test(raw) }
  const value = toMonthly(salaryAmount(singleMatch[1], singleMatch[2]), period)
  if (OPEN_MAX_RE.test(raw)) return { minMonthly: null, maxMonthly: value, negotiable: false }
  if (OPEN_MIN_RE.test(raw)) return { minMonthly: value, maxMonthly: null, negotiable: false }
  return { minMonthly: value, maxMonthly: value, negotiable: false }
}

export function salaryMatchesFilter(
  salaryText: string | null | undefined,
  state: SalaryFilterState,
): boolean {
  if (!salaryFilterActive(state)) return true

  const salary = parseSalaryRange(salaryText)
  if (salary.minMonthly === null && salary.maxMonthly === null) return state.includeUnknown

  const factor = state.unit === "annual" ? 12 : 1
  let wantedMin = inputAmount(state.min, factor)
  let wantedMax = inputAmount(state.max, factor)
  if (wantedMin !== null && wantedMax !== null && wantedMax < wantedMin) {
    [wantedMin, wantedMax] = [wantedMax, wantedMin]
  }
  const jobMin = salary.minMonthly ?? 0
  const jobMax = salary.maxMonthly ?? Number.POSITIVE_INFINITY
  return (
    jobMax >= (wantedMin ?? 0)
    && (wantedMax ?? Number.POSITIVE_INFINITY) >= jobMin
  )
}

function emptySalaryRange(): SalaryRange {
  return { minMonthly: null, maxMonthly: null, negotiable: false }
}

function salaryPeriod(text: string): SalaryUnit | null {
  if (ANNUAL_RE.test(text)) return "annual"
  if (MONTHLY_RE.test(text)) return "monthly"
  if (UNSUPPORTED_PERIOD_RE.test(text)) return null
  return "monthly"
}

function salaryAmount(raw: string, unit: string | undefined): number {
  const value = Number(raw.replaceAll(",", ""))
  if (unit === "萬" || unit === "万") return value * 10000
  if (unit?.toLowerCase() === "k") return value * 1000
  return value
}

function toMonthly(value: number, period: SalaryUnit): number {
  return roundMoney(period === "annual" ? value / 12 : value)
}

function inputAmount(value: string, factor: number): number | null {
  if (!value.trim()) return null
  const parsed = Number(value.replaceAll(",", ""))
  if (!Number.isFinite(parsed)) return null
  return roundMoney(Math.max(0, parsed) / factor)
}

function roundMoney(value: number): number {
  return Math.round(value * 100) / 100
}
