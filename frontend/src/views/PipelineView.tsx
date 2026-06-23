import { useEffect, useState } from "react"
import type { PipelineState, Seed } from "../types"
import { readSSE } from "../sse"
import { AgentTrace } from "../components/pipeline/AgentTrace"
import {
  MatchCard, CompanyCard, ResumeDoc, CoverLetterDoc, InterviewKitDoc, CritiqueCard,
} from "../components/pipeline/Documents"

type Phase = "idle" | "running" | "approval" | "done"

export function PipelineView({ seed }: { seed?: Seed | null }) {
  const [jd, setJd] = useState("")
  const [phase, setPhase] = useState<Phase>("idle")
  const [status, setStatus] = useState("")
  const [done, setDone] = useState<string[]>([])
  const [state, setState] = useState<PipelineState>({})
  const [threadId, setThreadId] = useState("")
  const [revisions, setRevisions] = useState(0)
  const [error, setError] = useState("")

  function handle(ev: any) {
    if (ev.type === "start") {
      setThreadId(ev.thread_id); setStatus("執行中…")
    } else if (ev.type === "node") {
      setDone((d) => [...d, ev.node])
      if (ev.data) setState((s) => ({ ...s, ...ev.data }))
      if (ev.node === "critic" && ev.data?.revision_count) setRevisions(ev.data.revision_count)
    } else if (ev.type === "interrupt") {
      setThreadId(ev.thread_id); setPhase("approval"); setStatus("待人工核可")
    } else if (ev.type === "done") {
      setPhase((p) => (p === "approval" ? p : "done")); setStatus("完成 ✅")
    } else if (ev.type === "error") {
      setError(ev.message || "發生錯誤")
    }
  }

  async function run(jdText: string = jd) {
    if (!jdText.trim()) return
    setError(""); setDone([]); setState({}); setRevisions(0); setPhase("running"); setStatus("啟動中…")
    try {
      const resp = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jdText }),
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

  // 從「自動找職缺」點選某職缺帶 JD 進來 → 自動開跑
  useEffect(() => {
    if (seed?.jd) { setJd(seed.jd); run(seed.jd) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.nonce])

  const hasDocs = Boolean(
    state.match_report || state.company_brief || state.tailored_resume ||
    state.cover_letter || state.interview_kit || state.critique,
  )

  return (
    <div>
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
