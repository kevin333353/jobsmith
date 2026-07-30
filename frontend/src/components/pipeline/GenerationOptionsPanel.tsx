import type { ComponentType } from "react"
import type { GenerationOptions, PackageArtifact } from "../../types"
import {
  COMPLETE_APPLICATION,
  INTERVIEW_PREP,
  QUICK_GENERATION,
  estimateGenerationCalls,
  normalizeGenerationOptions,
} from "../../lib/packageGeneration"
import { Building2, FileText, Mail, MessageSquare, ShieldCheck, Sparkles } from "../../ui/icons"

const PRESETS: {
  key: string
  label: string
  note: string
  options: GenerationOptions
}[] = [
  { key: "quick", label: "快速投遞", note: "只做客製履歷", options: QUICK_GENERATION },
  { key: "complete", label: "完整申請", note: "履歷＋求職信", options: COMPLETE_APPLICATION },
  { key: "interview", label: "面試準備", note: "公司情報＋面試題", options: INTERVIEW_PREP },
]

const OUTPUTS: {
  key: PackageArtifact
  label: string
  icon: ComponentType<{ className?: string }>
}[] = [
  { key: "resume", label: "客製履歷", icon: FileText },
  { key: "cover_letter", label: "求職信", icon: Mail },
  { key: "interview", label: "面試準備", icon: MessageSquare },
]

function sameOptions(a: GenerationOptions, b: GenerationOptions) {
  const left = normalizeGenerationOptions(a)
  const right = normalizeGenerationOptions(b)
  return left.companyResearch === right.companyResearch
    && left.qualityReview === right.qualityReview
    && left.artifactTargets.length === right.artifactTargets.length
    && left.artifactTargets.every((item) => right.artifactTargets.includes(item))
}

export function GenerationOptionsPanel(
  {
    value,
    onChange,
    reusesSearchAnalysis = false,
  }: {
    value: GenerationOptions
    onChange: (next: GenerationOptions) => void
    reusesSearchAnalysis?: boolean
  },
) {
  const normalized = normalizeGenerationOptions(value)
  const usesCompanyContext = normalized.artifactTargets.some(
    (item) => item === "cover_letter" || item === "interview",
  )
  const calls = estimateGenerationCalls(normalized, reusesSearchAnalysis)

  function toggleArtifact(target: PackageArtifact) {
    const selected = normalized.artifactTargets.includes(target)
    if (selected && normalized.artifactTargets.length === 1) return
    onChange(normalizeGenerationOptions({
      ...normalized,
      artifactTargets: selected
        ? normalized.artifactTargets.filter((item) => item !== target)
        : [...normalized.artifactTargets, target],
    }))
  }

  return (
    <section className="mt-4 border border-slate-200 rounded-xl p-3.5 bg-slate-50/70">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-brand-600" />
          <h3 className="text-sm font-semibold text-slate-800">這次要產出什麼？</h3>
        </div>
        <span className="ml-auto text-xs font-medium text-brand-700 bg-brand-50 border border-brand-100 rounded-full px-2.5 py-1">
          約 {calls} 次 AI 呼叫
        </span>
        {reusesSearchAnalysis && (
          <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-full px-2.5 py-1">
            已沿用搜尋分析
          </span>
        )}
      </div>

      <div className="grid sm:grid-cols-3 gap-2 mb-3">
        {PRESETS.map((preset) => {
          const active = sameOptions(normalized, preset.options)
          return (
            <button
              key={preset.key}
              type="button"
              aria-pressed={active}
              onClick={() => onChange({ ...preset.options, artifactTargets: [...preset.options.artifactTargets] })}
              className={`text-left rounded-lg border px-3 py-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                active
                  ? "border-brand-400 bg-white ring-1 ring-brand-200"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <span className={`block text-sm font-medium ${active ? "text-brand-700" : "text-slate-700"}`}>
                {preset.label}
              </span>
              <span className="block text-xs text-slate-500 mt-0.5">{preset.note}</span>
            </button>
          )
        })}
      </div>

      <div className="flex flex-wrap gap-2 mb-3" aria-label="產出文件">
        {OUTPUTS.map(({ key, label, icon: Icon }) => {
          const checked = normalized.artifactTargets.includes(key)
          return (
            <label
              key={key}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm cursor-pointer ${
                checked ? "border-brand-300 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600"
              }`}
            >
              <input
                type="checkbox"
                className="accent-brand-600"
                checked={checked}
                onChange={() => toggleArtifact(key)}
              />
              <Icon className="w-3.5 h-3.5" />{label}
            </label>
          )
        })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <label className={`inline-flex items-center gap-2 ${usesCompanyContext ? "text-slate-700" : "text-slate-400"}`}>
          <input
            type="checkbox"
            className="accent-brand-600"
            disabled={!usesCompanyContext}
            checked={normalized.companyResearch}
            onChange={(event) => onChange({ ...normalized, companyResearch: event.target.checked })}
          />
          <Building2 className="w-3.5 h-3.5" />
          公司情報 <span className="text-xs">＋1 次</span>
        </label>
        <label className="inline-flex items-center gap-2 text-slate-700">
          <input
            type="checkbox"
            className="accent-brand-600"
            checked={normalized.qualityReview}
            onChange={(event) => onChange({ ...normalized, qualityReview: event.target.checked })}
          />
          <ShieldCheck className="w-3.5 h-3.5" />
          AI 品管 <span className="text-xs text-slate-500">＋1 次，只給建議、不自動重寫</span>
        </label>
      </div>
    </section>
  )
}
