import { useEffect, useState } from "react"
import type { PipelineState, Seed, UserProfile, TelemetryEntry } from "../types"
import { readSSE } from "../sse"
import { AgentTrace } from "../components/pipeline/AgentTrace"
import {
  MatchCard, CompanyCard, ResumeDoc, CoverLetterDoc, InterviewKitDoc, CritiqueCard,
} from "../components/pipeline/Documents"

type Phase = "idle" | "running" | "approval" | "done"

export function PipelineView(
  { seed, fallbackProfile, onBack }:
  { seed?: Seed | null; fallbackProfile?: UserProfile | null; onBack?: () => void },
) {
  const [jd, setJd] = useState("")
  const [phase, setPhase] = useState<Phase>("idle")
  const [status, setStatus] = useState("")
  const [done, setDone] = useState<string[]>([])
  const [state, setState] = useState<PipelineState>({})
  const [threadId, setThreadId] = useState("")
  const [revisions, setRevisions] = useState(0)
  const [nodeErrors, setNodeErrors] = useState<{ node: string; message: string }[]>([])
  const [profileWarning, setProfileWarning] = useState("")
  const [telemetry, setTelemetry] = useState<TelemetryEntry[]>([])
  const [error, setError] = useState("")

  function handle(ev: any) {
    if (ev.type === "start") {
      setThreadId(ev.thread_id); setStatus("執行中…")
    } else if (ev.type === "node") {
      setDone((d) => [...d, ev.node])
      if (ev.data) setState((s) => ({ ...s, ...ev.data }))
      if (ev.node === "critic" && ev.data?.revision_count) setRevisions(ev.data.revision_count)
    } else if (ev.type === "node_error") {
      setNodeErrors((e) => [...e, { node: ev.node, message: ev.message }])
    } else if (ev.type === "profile_warning") {
      setProfileWarning(ev.message)
    } else if (ev.type === "telemetry") {
      setTelemetry((t) => [...t, ev as TelemetryEntry])
    } else if (ev.type === "interrupt") {
      setThreadId(ev.thread_id); setPhase("approval"); setStatus("待人工核可")
    } else if (ev.type === "done") {
      setPhase((p) => (p === "approval" ? p : "done")); setStatus("完成 ✅")
    } else if (ev.type === "error") {
      setError(ev.message || "發生錯誤"); setPhase("done"); setStatus("")
    }
  }

  async function run(jdText: string = jd, profile?: UserProfile | null) {
    if (!jdText.trim()) return
    // 手動開跑（無 seed）時改用共用的真實履歷；都沒有才讓後端用範例 demo 並提醒。
    const effectiveProfile = profile ?? fallbackProfile ?? null
    setError(""); setNodeErrors([]); setProfileWarning(""); setTelemetry([]); setDone([]); setState({}); setRevisions(0)
    setPhase("running"); setStatus("啟動中…")
    try {
      const resp = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jdText, profile: effectiveProfile }),
      })
      await readSSE(resp, handle)
      setPhase((p) => (p === "approval" ? p : "done"))
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。"); setPhase("idle")
    }
  }

  async function decide(decision: "y" | "n") {
    setPhase("running"); setStatus(decision === "y" ? "核可中…" : "退回中…")
    try {
      const resp = await fetch("/api/resume", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, decision }),
      })
      await readSSE(resp, handle)
      setPhase("done")
    } catch {
      setError("連線發生問題。")
    }
  }

  async function loadSample() {
    const j = await (await fetch("/api/sample")).json()
    setJd(j.jd_text)
  }

  // 從「自動找職缺」點選某職缺帶 JD + 真實履歷進來 → 自動開跑（投遞包用本人背景）
  useEffect(() => {
    if (seed?.jd) { setJd(seed.jd); run(seed.jd, seed.profile) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.nonce])

  const hasDocs = Boolean(
    state.match_report || state.company_brief || state.tailored_resume ||
    state.cover_letter || state.interview_kit || state.critique,
  )

  return (
    <div>
      {onBack && (
        <button onClick={onBack} className="no-print text-sm text-indigo-600 mb-3">← 回職缺列表</button>
      )}
      <div className="no-print mb-4 bg-white border rounded-xl p-5">
        <textarea
          className="w-full border rounded-lg p-3 text-sm h-32"
          placeholder="貼上職缺 JD 文字…"
          value={jd}
          onChange={(e) => setJd(e.target.value)}
        />
        <div className="flex flex-wrap gap-2 mt-3 items-center">
          <button onClick={() => run()} disabled={phase === "running" || !jd.trim()}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
            開始（跑 8 個 agent）
          </button>
          <button onClick={loadSample} disabled={phase === "running"}
            className="px-4 py-2 bg-slate-200 rounded-lg text-sm">載入範例 JD</button>
          {hasDocs && (
            <button onClick={() => window.print()}
              className="px-4 py-2 bg-slate-200 rounded-lg text-sm">列印 / 匯出 PDF</button>
          )}
        </div>
        {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
      </div>

      <div className="grid lg:grid-cols-[260px_1fr] gap-6 print:block">
        <aside className="no-print">
          <AgentTrace done={done} running={phase === "running"} revisions={revisions} status={status} />
        </aside>
        <main className="space-y-4">
          {telemetry.length > 0 && (() => {
            const tot = telemetry.reduce(
              (a, t) => ({
                calls: a.calls + (t.calls || 0),
                tokens: a.tokens + (t.input_tokens || 0) + (t.output_tokens || 0),
                cost: a.cost + (t.cost_usd || 0),
                ms: a.ms + (t.latency_ms || 0),
              }),
              { calls: 0, tokens: 0, cost: 0, ms: 0 },
            )
            return (
              <div className="text-xs text-slate-500 bg-white border rounded-lg px-3 py-2 flex flex-wrap gap-x-4 gap-y-1">
                <span>⚙️ {telemetry.length} 個 agent</span>
                <span>{tot.calls} 次 LLM 呼叫</span>
                <span>{tot.tokens.toLocaleString()} tokens</span>
                {tot.cost > 0 && <span>${tot.cost.toFixed(4)}</span>}
                <span>{(tot.ms / 1000).toFixed(1)}s</span>
              </div>
            )
          })()}
          {profileWarning && (
            <div className="border-2 border-amber-300 bg-amber-50 rounded-xl p-3 text-sm text-amber-800">
              ⚠️ {profileWarning}
            </div>
          )}
          {phase === "approval" && (
            <div className="no-print border-2 border-indigo-300 bg-indigo-50 rounded-xl p-4 flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium">這份投遞包要核可嗎？</span>
              <button onClick={() => decide("y")}
                className="px-3 py-1 bg-emerald-600 text-white rounded text-sm">核可</button>
              <button onClick={() => decide("n")}
                className="px-3 py-1 bg-rose-600 text-white rounded text-sm">退回重做</button>
            </div>
          )}
          {state.approved === true && <div className="no-print text-sm text-emerald-700">✅ 已核可</div>}
          {state.approved === false && <div className="no-print text-sm text-rose-700">↩︎ 已退回</div>}

          {nodeErrors.length > 0 && (
            <div className="no-print bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
              <p className="font-medium mb-1">部分環節降級（已用替代內容續跑，可重試提升品質）</p>
              <ul className="list-disc pl-5 space-y-0.5">
                {nodeErrors.map((e, i) => <li key={i}>{e.node}：{e.message}</li>)}
              </ul>
            </div>
          )}

          {state.match_report && <MatchCard m={state.match_report} />}
          {state.company_brief && <CompanyCard c={state.company_brief} />}
          {state.tailored_resume && <ResumeDoc r={state.tailored_resume} />}
          {state.cover_letter && <CoverLetterDoc c={state.cover_letter} />}
          {state.interview_kit && <InterviewKitDoc k={state.interview_kit} />}
          {state.critique && <CritiqueCard q={state.critique} />}

          {!hasDocs && phase !== "running" && (
            <p className="text-slate-400 text-sm">貼上 JD 後按「開始」，這裡會即時長出投遞包成品（履歷／求職信／面試／公司情報）。</p>
          )}
        </main>
      </div>
    </div>
  )
}
