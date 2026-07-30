import { useId, useMemo, useState } from "react"
import type { ReactNode } from "react"
import type { JobMatch } from "../../types"
import { SRC_LABEL } from "../../lib/sources"
import { Card } from "../../ui/Card"
import { ChevronDown, Settings2, X } from "../../ui/icons"
import { EXPERIENCE_FILTER_OPTIONS } from "./experience"
import { FIT_FILTERS } from "./fitFilter"
import { salaryFilterActive } from "./salaryFilter"
import {
  createEmptyResultRefinement,
  RESULT_WORK_MODE_OPTIONS,
  RESULT_WORK_MODE_ORIGIN_OPTIONS,
  type ResultRefinementState,
  type ResultWorkMode,
  type ResultWorkModeOrigin,
} from "./resultRefinement"

type Props = {
  matches: JobMatch[]
  value: ResultRefinementState
  visibleCount: number
  onChange: (next: ResultRefinementState) => void
  helpText?: string
}

type ActiveChip = {
  key: string
  label: string
  remove: () => void
}

const fieldClass = "w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
const toggleBase = "rounded-lg border px-2.5 py-1 text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"

const DEFAULT_HELP_TEXT = "這些條件只篩選目前資料池，不會重新連線或使用 AI；若要找更多職缺，請調整上方「搜尋範圍」。"

export function ResultRefinementBar(
  { matches, value, visibleCount, onChange, helpText = DEFAULT_HELP_TEXT }: Props,
) {
  const [expanded, setExpanded] = useState(false)
  const panelId = useId()
  const availableSources = useMemo(() => (
    [...new Set(matches.map((match) => match.job.source))]
      .sort((a, b) => sourceLabel(a).localeCompare(sourceLabel(b), "zh-Hant"))
  ), [matches])
  const availableWorkModes = useMemo(() => (
    new Set(matches.map((match) => match.job.work_mode || "unknown"))
  ), [matches])
  const availableOrigins = useMemo(() => (
    new Set(matches.map((match) => match.job.work_mode_origin || "unknown"))
  ), [matches])
  const workModeOptions = RESULT_WORK_MODE_OPTIONS.filter((option) => (
    availableWorkModes.has(option.value)
  ))
  const originOptions = RESULT_WORK_MODE_ORIGIN_OPTIONS.filter((option) => (
    availableOrigins.has(option.value)
  ))

  function patch(next: Partial<ResultRefinementState>) {
    onChange({ ...value, ...next })
  }

  function toggleSource(source: string) {
    patch({
      sources: value.sources.includes(source)
        ? value.sources.filter((item) => item !== source)
        : [...value.sources, source],
    })
  }

  function toggleWorkMode(mode: ResultWorkMode) {
    patch({
      workModes: value.workModes.includes(mode)
        ? value.workModes.filter((item) => item !== mode)
        : [...value.workModes, mode],
    })
  }

  function toggleOrigin(origin: ResultWorkModeOrigin) {
    patch({
      workModeOrigins: value.workModeOrigins.includes(origin)
        ? value.workModeOrigins.filter((item) => item !== origin)
        : [...value.workModeOrigins, origin],
    })
  }

  const activeChips: ActiveChip[] = []
  if (value.query.trim()) {
    activeChips.push({
      key: "query",
      label: `關鍵字：${compact(value.query)}`,
      remove: () => patch({ query: "" }),
    })
  }
  if (value.location.trim()) {
    activeChips.push({
      key: "location",
      label: `地點：${compact(value.location)}`,
      remove: () => patch({ location: "" }),
    })
  }
  for (const source of value.sources) {
    activeChips.push({
      key: `source-${source}`,
      label: `來源：${sourceLabel(source)}`,
      remove: () => toggleSource(source),
    })
  }
  for (const mode of value.workModes) {
    activeChips.push({
      key: `mode-${mode}`,
      label: workModeLabel(mode),
      remove: () => toggleWorkMode(mode),
    })
  }
  for (const origin of value.workModeOrigins) {
    activeChips.push({
      key: `origin-${origin}`,
      label: workModeOriginLabel(origin),
      remove: () => toggleOrigin(origin),
    })
  }
  if (value.minFit) {
    const label = FIT_FILTERS.find((option) => option.value === value.minFit)?.label || value.minFit
    activeChips.push({
      key: "fit",
      label: `適配：${label}`,
      remove: () => patch({ minFit: 0 }),
    })
  }
  if (value.maxExperienceYears !== "") {
    const label = EXPERIENCE_FILTER_OPTIONS.find(
      (option) => option.value === value.maxExperienceYears,
    )?.label
    activeChips.push({
      key: "experience",
      label: label || `年資上限 ${value.maxExperienceYears} 年`,
      remove: () => patch({ maxExperienceYears: "" }),
    })
  }
  const salaryState = {
    unit: value.salaryUnit,
    min: value.minSalary,
    max: value.maxSalary,
    includeUnknown: value.includeUnknownSalary,
  }
  if (salaryFilterActive(salaryState)) {
    activeChips.push({
      key: "salary",
      label: salaryChipLabel(value),
      remove: () => patch({
        minSalary: "",
        maxSalary: "",
        includeUnknownSalary: true,
      }),
    })
  }

  return (
    <Card className="mb-3 overflow-hidden border-brand-100">
      <div className="flex min-h-12 flex-wrap items-center gap-2 px-3 py-2.5">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
          <Settings2 className="h-4 w-4" />
        </span>
        <div className="flex min-w-0 flex-1 items-baseline gap-2">
          <h3 className="shrink-0 text-sm font-semibold text-slate-900">篩選目前結果</h3>
          <span className="hidden truncate text-xs text-slate-400 sm:inline">
            本地即時篩選，不重跑 AI
          </span>
        </div>
        <div
          aria-live="polite"
          aria-label={`顯示 ${visibleCount} / ${matches.length} 筆職缺`}
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
            visibleCount === 0
              ? "bg-amber-50 text-amber-700"
              : "bg-brand-50 text-brand-800"
          }`}
        >
          <strong>{visibleCount}</strong> / {matches.length} 筆
        </div>
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => setExpanded((current) => !current)}
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
        >
          {expanded ? "收合" : "篩選"}
          {activeChips.length > 0 && (
            <span className="grid h-4 min-w-4 place-items-center rounded-full bg-brand-100 px-1 text-[10px] text-brand-700">
              {activeChips.length}
            </span>
          )}
          <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition ${expanded ? "rotate-180" : ""}`} />
        </button>
      </div>

      {activeChips.length > 0 && (
        <div className="flex min-w-0 items-center gap-2 border-t border-slate-100 px-3 py-2">
          <span className="shrink-0 text-[11px] text-slate-400">已套用</span>
          <div className="min-w-0 flex-1 overflow-x-auto">
            <div className="flex w-max items-center gap-1.5 pr-2">
              {activeChips.map((chip) => (
                <button
                  key={chip.key}
                  type="button"
                  onClick={chip.remove}
                  aria-label={`移除篩選：${chip.label}`}
                  className="inline-flex shrink-0 items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
                >
                  {chip.label}<X className="h-3 w-3" />
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onChange(createEmptyResultRefinement())}
            className="shrink-0 rounded px-1.5 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
          >
            清除
          </button>
        </div>
      )}

      {expanded && (
        <div
          id={panelId}
          className="border-t border-slate-200 bg-slate-50/60 px-3 pb-3 pt-3"
        >
          <div className="grid gap-3 lg:grid-cols-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-600">
                職稱、公司或內容
              </span>
              <input
                type="search"
                value={value.query}
                onChange={(event) => patch({ query: event.target.value })}
                placeholder="例如：Python、RAG、新創"
                className={fieldClass}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-600">地點包含</span>
              <input
                type="search"
                value={value.location}
                onChange={(event) => patch({ location: event.target.value })}
                placeholder="例如：台北、新竹、台灣"
                className={fieldClass}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-600">
                最高可接受要求年資
              </span>
              <select
                value={value.maxExperienceYears}
                onChange={(event) => patch({ maxExperienceYears: event.target.value })}
                className={fieldClass}
              >
                {EXPERIENCE_FILTER_OPTIONS.map((option) => (
                  <option key={option.value || "all"} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-3">
            <span className="mb-1 block text-xs font-medium text-slate-600">薪資範圍</span>
            <div className="flex flex-wrap items-center gap-2">
              <select
                aria-label="結果薪資單位"
                value={value.salaryUnit}
                onChange={(event) => patch({
                  salaryUnit: event.target.value === "annual" ? "annual" : "monthly",
                })}
                className={`${fieldClass} w-auto`}
              >
                <option value="monthly">月薪</option>
                <option value="annual">年薪</option>
              </select>
              <input
                type="number"
                min="0"
                step="1000"
                inputMode="numeric"
                aria-label={value.salaryUnit === "annual" ? "結果最低年薪" : "結果最低月薪"}
                value={value.minSalary}
                onChange={(event) => patch({ minSalary: event.target.value })}
                placeholder="最低"
                className={`${fieldClass} w-28`}
              />
              <span className="text-slate-400">–</span>
              <input
                type="number"
                min="0"
                step="1000"
                inputMode="numeric"
                aria-label={value.salaryUnit === "annual" ? "結果最高年薪" : "結果最高月薪"}
                value={value.maxSalary}
                onChange={(event) => patch({ maxSalary: event.target.value })}
                placeholder="最高"
                className={`${fieldClass} w-28`}
              />
              <label className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                <input
                  type="checkbox"
                  checked={value.includeUnknownSalary}
                  onChange={(event) => patch({ includeUnknownSalary: event.target.checked })}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-300"
                />
                保留面議 / 未標示
              </label>
            </div>
          </div>

          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <FilterGroup label="適配度" ariaLabel="結果適配度篩選">
              {FIT_FILTERS.map((option) => (
                <FilterToggle
                  key={option.value}
                  pressed={value.minFit === option.value}
                  onClick={() => patch({ minFit: option.value })}
                >
                  {option.label}
                </FilterToggle>
              ))}
            </FilterGroup>

            <FilterGroup label="職缺來源" ariaLabel="結果來源篩選">
              <FilterToggle
                pressed={value.sources.length === 0}
                onClick={() => patch({ sources: [] })}
              >
                全部來源
              </FilterToggle>
              {availableSources.map((source) => (
                <FilterToggle
                  key={source}
                  pressed={value.sources.includes(source)}
                  onClick={() => toggleSource(source)}
                >
                  {sourceLabel(source)}
                </FilterToggle>
              ))}
            </FilterGroup>

            <FilterGroup label="工作型態" ariaLabel="結果工作型態篩選">
              <FilterToggle
                pressed={value.workModes.length === 0}
                onClick={() => patch({ workModes: [] })}
              >
                全部型態
              </FilterToggle>
              {workModeOptions.map((option) => (
                <FilterToggle
                  key={option.value}
                  pressed={value.workModes.includes(option.value)}
                  onClick={() => toggleWorkMode(option.value)}
                >
                  {option.label}
                </FilterToggle>
              ))}
            </FilterGroup>

            <FilterGroup label="判斷依據" ariaLabel="結果工作型態判斷依據篩選">
              <FilterToggle
                pressed={value.workModeOrigins.length === 0}
                onClick={() => patch({ workModeOrigins: [] })}
              >
                全部依據
              </FilterToggle>
              {originOptions.map((option) => (
                <FilterToggle
                  key={option.value}
                  pressed={value.workModeOrigins.includes(option.value)}
                  onClick={() => toggleOrigin(option.value)}
                >
                  {option.label}
                </FilterToggle>
              ))}
            </FilterGroup>
          </div>

          <p className="mt-3 text-xs text-slate-400">
            {helpText}
          </p>
        </div>
      )}
    </Card>
  )
}

function FilterGroup(
  { label, ariaLabel, children }:
  { label: string; ariaLabel: string; children: ReactNode },
) {
  return (
    <div>
      <span className="mb-1.5 block text-xs font-medium text-slate-600">{label}</span>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={ariaLabel}>
        {children}
      </div>
    </div>
  )
}

function FilterToggle(
  { pressed, onClick, children }:
  { pressed: boolean; onClick: () => void; children: ReactNode },
) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      className={`${toggleBase} ${
        pressed
          ? "border-brand-600 bg-brand-600 text-white"
          : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  )
}

function sourceLabel(source: string): string {
  return SRC_LABEL[source] || source
}

function workModeLabel(mode: ResultWorkMode): string {
  return RESULT_WORK_MODE_OPTIONS.find((option) => option.value === mode)?.label || mode
}

function workModeOriginLabel(origin: ResultWorkModeOrigin): string {
  return RESULT_WORK_MODE_ORIGIN_OPTIONS.find((option) => option.value === origin)?.label || origin
}

function compact(value: string): string {
  const trimmed = value.trim()
  return trimmed.length > 24 ? `${trimmed.slice(0, 24)}…` : trimmed
}

function salaryChipLabel(value: ResultRefinementState): string {
  const unit = value.salaryUnit === "annual" ? "年薪" : "月薪"
  const min = value.minSalary.trim()
  const max = value.maxSalary.trim()
  let range = "只看有標示薪資"
  if (min && max) range = `${unit} ${formatAmount(min)}–${formatAmount(max)}`
  else if (min) range = `${unit} ${formatAmount(min)} 以上`
  else if (max) range = `${unit} ${formatAmount(max)} 以下`
  return value.includeUnknownSalary && (min || max) ? `${range}（含未標示）` : range
}

function formatAmount(value: string): string {
  const parsed = Number(value.replaceAll(",", ""))
  return Number.isFinite(parsed) ? new Intl.NumberFormat("zh-TW").format(parsed) : value
}
