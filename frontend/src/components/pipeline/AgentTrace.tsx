import type { ComponentType } from "react"
import type { GenerationOptions, TelemetryEntry } from "../../types"
import {
  Search, Target, Building2, FileText, Mail, MessageSquare, ShieldCheck,
  Sparkles, CheckCircle2, Loader2, AlertTriangle,
  Cpu, Timer, Network, Gauge,
} from "../../ui/icons"

type Kind = "agent" | "decision" | "gate"
interface NodeDef { key: string; label: string; icon: ComponentType<{ className?: string }>; kind: Kind }

const PARSE: NodeDef = { key: "parse", label: "解析 JD", icon: Search, kind: "agent" }
const MATCH: NodeDef = { key: "match", label: "匹配評分", icon: Target, kind: "agent" }
const SUP_MATCH: NodeDef = { key: "supervisor_match", label: "適配門檻 · 是否續做", icon: Sparkles, kind: "decision" }
const COMPANY: NodeDef = { key: "company_research", label: "公司情報", icon: Building2, kind: "agent" }
const GEN: NodeDef[] = [
  { key: "resume_tailor", label: "客製履歷", icon: FileText, kind: "agent" },
  { key: "cover_letter", label: "求職信", icon: Mail, kind: "agent" },
  { key: "interview_prep", label: "面試準備", icon: MessageSquare, kind: "agent" },
]
const CRITIC: NodeDef = { key: "critic", label: "AI 品管建議", icon: ShieldCheck, kind: "agent" }
const GATE: NodeDef = { key: "human_gate", label: "完成並存檔", icon: CheckCircle2, kind: "gate" }

type Status = "pending" | "active" | "done" | "error"

// 只依本次選取的節點推斷進度；後端雖會送出靜態圖中「略過」節點的空事件，介面不顯示它們。
function computeActive(
  done: string[],
  running: boolean,
  genKeys: string[],
  companyResearch: boolean,
  qualityReview: boolean,
): Set<string> {
  if (!running) return new Set()
  const relevant = new Set([
    "parse", "match", "supervisor_match", "join", "human_gate",
    ...(companyResearch ? ["company_research"] : []),
    ...(qualityReview ? ["critic"] : []),
    ...genKeys,
  ])
  const completed = done.filter((key) => relevant.has(key))
  if (!completed.length) return new Set(["parse"])
  const last = completed[completed.length - 1]
  const one = (k: string) => new Set([k])
  const afterGeneration = () => one(qualityReview ? "critic" : "human_gate")
  switch (last) {
    case "parse": return one("match")
    case "match": return one("supervisor_match")
    case "supervisor_match":
      return companyResearch ? one("company_research") : new Set(genKeys)
    case "join": return afterGeneration()
    case "critic": return one("human_gate")
    case "human_gate": return new Set()
  }
  if (last === "company_research") return new Set(genKeys)
  if (genKeys.includes(last)) {
    const doneGen = new Set(completed.filter((key) => genKeys.includes(key)))
    const remaining = genKeys.filter((key) => !doneGen.has(key))
    return remaining.length ? new Set(remaining) : afterGeneration()
  }
  return new Set()
}

function statusStyle(s: Status) {
  switch (s) {
    case "done": return "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30"
    case "active": return "bg-brand-500/25 text-brand-100 ring-brand-300/60 animate-pulse-node"
    case "error": return "bg-amber-500/15 text-amber-300 ring-amber-400/30"
    default: return "bg-white/5 text-slate-400 ring-white/10"
  }
}

// 大數字壓縮顯示，避免 token 數撐破統計框（如 303,636 → 304K）。
function compact(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1).replace(/\.0$/, "") + "M"
  if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1).replace(/\.0$/, "") + "K"
  return String(n)
}

// 耗時人性化顯示：避免「149.3s」這種看不出多久、又會撐破框的原始秒數。
// <60 秒 → 「48 秒」；≥60 秒 → 「2 分 29 秒」。
function fmtDuration(ms: number): string {
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s} 秒`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem ? `${m} 分 ${rem} 秒` : `${m} 分`
}

function NodeBadges({ t }: { t?: TelemetryEntry }) {
  if (!t) return null
  const tokens = (t.input_tokens || 0) + (t.output_tokens || 0)
  const items: [ComponentType<{ className?: string }>, string][] = []
  if (tokens > 0) items.push([Cpu, compact(tokens)])
  if (t.latency_ms > 0) items.push([Timer, fmtDuration(t.latency_ms)])
  if (!items.length) return null
  return (
    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 mt-1 text-[11px] text-slate-400">
      {items.map(([Icon, val], i) => (
        <span key={i} className="inline-flex items-center gap-1">
          <Icon className="w-3 h-3" />{val}
        </span>
      ))}
    </div>
  )
}

function NodeRow(
  { node, status, telem, connector }:
  { node: NodeDef; status: Status; telem?: TelemetryEntry; connector: boolean },
) {
  const Icon = status === "active" ? Loader2 : status === "error" ? AlertTriangle : node.icon
  const diamond = node.kind === "decision"
  return (
    <li className="relative flex gap-3">
      <div className="relative flex flex-col items-center">
        <span
          className={`grid place-items-center w-9 h-9 ring-1 ${statusStyle(status)} ${
            diamond ? "rounded-md rotate-45" : "rounded-xl"
          }`}
        >
          <Icon className={`w-[18px] h-[18px] ${diamond ? "-rotate-45" : ""} ${status === "active" ? "animate-spin" : ""}`} />
        </span>
        {connector && <span className="w-px flex-1 min-h-[14px] bg-white/10 my-1" />}
      </div>
      <div className="flex-1 pb-3 pt-1.5">
        <p className={`text-sm leading-tight ${
          status === "pending" ? "text-slate-400" : "text-slate-100"
        } ${node.kind === "decision" ? "text-brand-200" : ""}`}>
          {node.label}
        </p>
        <NodeBadges t={telem} />
      </div>
    </li>
  )
}

function Stat(
  { icon: Icon, label, value, hint }:
  { icon: ComponentType<{ className?: string }>; label: string; value: string; hint?: string },
) {
  return (
    <div title={hint}
      className={`flex items-center gap-2 bg-white/5 rounded-lg px-2.5 py-1.5 min-w-0 ${hint ? "cursor-help" : ""}`}>
      <Icon className="w-3.5 h-3.5 text-brand-300 shrink-0" />
      <div className="leading-tight min-w-0">
        <div className="text-sm font-semibold text-white truncate">{value}</div>
        <div className="text-[10px] text-slate-400 truncate">{label}</div>
      </div>
    </div>
  )
}

export function AgentTrace(
  { done, running, status, options, telemetry = [], nodeErrors = [] }:
  {
    done: string[]
    running: boolean
    status: string
    options: GenerationOptions
    telemetry?: TelemetryEntry[]
    nodeErrors?: { node: string; message: string }[]
  },
) {
  const selectedGen = GEN.filter((node) => {
    if (node.key === "resume_tailor") return options.artifactTargets.includes("resume")
    if (node.key === "cover_letter") return options.artifactTargets.includes("cover_letter")
    return options.artifactTargets.includes("interview")
  })
  const genKeys = selectedGen.map((node) => node.key)
  const seen = new Set(done)
  const errSet = new Set(nodeErrors.map((e) => e.node))

  // 每節點 telemetry 加總（重連重播或未來重試時也能正確彙整）。
  const byNode = new Map<string, TelemetryEntry>()
  for (const t of telemetry) {
    const e = byNode.get(t.node)
    if (e) {
      e.calls += t.calls; e.input_tokens += t.input_tokens
      e.output_tokens += t.output_tokens; e.latency_ms += t.latency_ms
    } else {
      byNode.set(t.node, { ...t })
    }
  }
  const totals = telemetry.reduce(
    (a, t) => ({
      tokens: a.tokens + (t.input_tokens || 0) + (t.output_tokens || 0),
      ms: a.ms + (t.latency_ms || 0),
    }),
    { tokens: 0, ms: 0 },
  )
  const hasTelem = byNode.size > 0

  const active = computeActive(
    done,
    running,
    genKeys,
    options.companyResearch,
    options.qualityReview,
  )
  function statusOf(key: string): Status {
    if (active.has(key)) return "active"
    if (errSet.has(key)) return "error"
    if (seen.has(key)) return "done"
    return "pending"
  }

  const single = (n: NodeDef, connector = true) => (
    <NodeRow key={n.key} node={n} status={statusOf(n.key)} telem={byNode.get(n.key)} connector={connector} />
  )
  const genActive = genKeys.some((key) => statusOf(key) === "active")

  return (
    <div className="no-print sticky top-4 rounded-xl2 bg-gradient-to-b from-slate-900 to-slate-800 text-slate-100 shadow-glow ring-1 ring-white/10 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Network className="w-4 h-4 text-brand-300" />
        <h2 className="font-semibold text-sm text-white">本次產出流程</h2>
      </div>

      {hasTelem && (
        <div className="grid grid-cols-3 gap-2 mb-4">
          <Stat icon={Gauge} label="agents" value={String(byNode.size)} />
          <Stat icon={Cpu} label="tokens" value={compact(totals.tokens)}
            hint="各步驟回報的輸入與輸出 token 合計" />
          <Stat icon={Timer} label="時間" value={fmtDuration(totals.ms)} />
        </div>
      )}

      <ol className="relative">
        {single(PARSE)}
        {single(MATCH)}
        {single(SUP_MATCH)}
        {options.companyResearch && single(COMPANY)}

        {/* 並行生成群組 */}
        <li className="relative flex gap-3">
          <div className="relative flex flex-col items-center">
            <span className={`grid place-items-center w-9 h-9 rounded-xl ring-1 ${
              genActive ? "bg-brand-500/25 text-brand-100 ring-brand-300/60 animate-pulse-node"
                : genKeys.every((key) => seen.has(key)) ? "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30"
                  : "bg-white/5 text-slate-500 ring-white/10"
            }`}>
              <Network className="w-[18px] h-[18px]" />
            </span>
            <span className="w-px flex-1 min-h-[14px] bg-white/10 my-1" />
          </div>
          <div className="flex-1 pb-3 pt-1.5">
            <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2">
              按需生成 · {selectedGen.length} {selectedGen.length === 1 ? "agent" : "agents"}
            </p>
            <div className="rounded-lg bg-white/[0.03] ring-1 ring-white/5 p-2 space-y-2">
              {selectedGen.map((n) => {
                const s = statusOf(n.key)
                const Icon = s === "active" ? Loader2 : s === "error" ? AlertTriangle : n.icon
                const t = byNode.get(n.key)
                return (
                  <div key={n.key} className="flex items-start gap-2">
                    <span className={`grid place-items-center w-6 h-6 rounded-lg ring-1 shrink-0 ${statusStyle(s)}`}>
                      <Icon className={`w-3.5 h-3.5 ${s === "active" ? "animate-spin" : ""}`} />
                    </span>
                    <div className="min-w-0">
                      <p className={`text-xs leading-tight ${s === "pending" ? "text-slate-500" : "text-slate-100"}`}>{n.label}</p>
                      <NodeBadges t={t} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </li>

        {options.qualityReview && single(CRITIC)}
        {single(GATE, false)}
      </ol>

      <p className="text-xs text-slate-400 mt-1 flex items-center gap-1.5">
        {running && <Loader2 className="w-3 h-3 animate-spin" />}
        {status || (seen.size === 0 ? "等待開始…" : "")}
      </p>
    </div>
  )
}
