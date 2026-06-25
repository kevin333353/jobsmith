import { useEffect, useState } from "react"
import type { PipelineState, Seed, UserProfile, TelemetryEntry, EditablePackage, Preferences, PipelineEvent } from "../types"
import { readSSE } from "../sse"
import { AgentTrace } from "../components/pipeline/AgentTrace"
import {
  MatchCard, CompanyCard, ResumeDoc, CoverLetterDoc, InterviewKitDoc, CritiqueCard,
} from "../components/pipeline/Documents"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { EmptyState } from "../ui/EmptyState"
import {
  Sparkles, Network, ArrowLeft, AlertTriangle, CheckCircle2, RefreshCw, Printer, LinkIcon,
  Pencil, FileDown,
} from "../ui/icons"

type Phase = "idle" | "running" | "approval" | "done"

export function PipelineView(
  { seed, fallbackProfile, preferences, onBack }:
  { seed?: Seed | null; fallbackProfile?: UserProfile | null; preferences?: Preferences; onBack?: () => void },
) {
  const [jd, setJd] = useState("")
  const [url, setUrl] = useState("")
  const [fetching, setFetching] = useState(false)
  const [fetchErr, setFetchErr] = useState("")
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
  const [editing, setEditing] = useState(false)
  const [edited, setEdited] = useState<EditablePackage | null>(null)
  const [wantPrint, setWantPrint] = useState(false)

  function handle(ev: PipelineEvent) {
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
    setEditing(false); setEdited(null)
    setPhase("running"); setStatus("啟動中…")
    try {
      const resp = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jdText, profile: effectiveProfile, preferences: preferences ?? null }),
      })
      await readSSE(resp, handle)
      setPhase((p) => (p === "approval" ? p : "done"))
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。"); setPhase("idle")
    }
  }

  async function decide(decision: "y" | "n") {
    // 退回重做會重新生成成品 → 丟棄上一輪的編輯，避免舊編輯值靜默覆蓋新成品。
    if (decision === "n") { setEditing(false); setEdited(null) }
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

  // 貼職缺網址 → 後端抽取 JD 文字（104 走官方 API，其餘通用抽取）→ 填入文字框。
  async function fetchUrl() {
    if (!url.trim() || fetching) return
    setFetching(true); setFetchErr("")
    try {
      const r = await fetch("/api/jd/fetch", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      })
      const d = await r.json()
      if (!r.ok) { setFetchErr(d.error || "抓取失敗，請改貼 JD 文字。"); return }
      const head = [d.title, d.company ? `公司：${d.company}` : ""].filter(Boolean).join("\n")
      setJd((head ? head + "\n\n" : "") + (d.text || ""))
    } catch {
      setFetchErr("連線發生問題，請改貼 JD 文字。")
    } finally {
      setFetching(false)
    }
  }

  const patch = (p: Partial<EditablePackage>) => setEdited((e) => (e ? { ...e, ...p } : e))

  // 進入編輯模式時，從目前成品初始化可編輯欄位（之後讀／印／匯出都用編輯後的值）。
  function toggleEdit() {
    if (!editing && !edited) {
      setEdited({
        resumeSummary: state.tailored_resume?.summary ?? "",
        resumeBullets: (state.tailored_resume?.bullets ?? []).join("\n"),
        coverSubject: state.cover_letter?.subject ?? "",
        coverBody: state.cover_letter?.body ?? "",
      })
    }
    setEditing((v) => !v)
  }

  function buildPkg() {
    const r = state.tailored_resume, c = state.cover_letter, k = state.interview_kit
    return {
      job_title: state.parsed_job?.title || "求職投遞包",
      company: state.parsed_job?.company || state.company_brief?.company || "",
      resume: r ? {
        summary: edited ? edited.resumeSummary : r.summary,
        bullets: edited ? edited.resumeBullets.split("\n").filter((b) => b.trim()) : r.bullets,
        ats_keywords_hit: r.ats_keywords_hit,
      } : undefined,
      cover_letter: c ? {
        subject: edited ? edited.coverSubject : (c.subject ?? ""),
        body: edited ? edited.coverBody : c.body,
      } : undefined,
      interview: k ?? undefined,
    }
  }

  async function downloadDocx() {
    try {
      const r = await fetch("/api/export/docx", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPkg()),
      })
      if (!r.ok) { setError("匯出失敗，請重試。"); return }
      const blob = await r.blob()
      const a = document.createElement("a")
      a.href = URL.createObjectURL(blob)
      a.download = "投遞包.docx"
      a.click()
      URL.revokeObjectURL(a.href)
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。")
    }
  }

  // 列印前先退出編輯模式（編輯值已存在 edited，唯讀檢視仍顯示），避免印出 textarea。
  // 退出編輯需先 render（textarea→唯讀）再 print，故經由 wantPrint 旗標延一個 render。
  function printDocs() { setEditing(false); setWantPrint(true) }
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (wantPrint) { setWantPrint(false); window.print() }
  }, [wantPrint])

  // 從「自動找職缺」點選某職缺帶 JD + 真實履歷進來 → 自動開跑（投遞包用本人背景）。
  // 由父層的 seed.nonce 觸發（外部訊號），是 effect 的正當用途。
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
        <button onClick={onBack}
          className="no-print text-sm text-brand-600 hover:text-brand-700 mb-3 inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />回職缺列表
        </button>
      )}
      <Card className="no-print mb-4 p-5">
        <div className="flex gap-2 mb-3">
          <div className="relative flex-1">
            <LinkIcon className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") fetchUrl() }}
              placeholder="貼職缺網址（104 或一般網頁）自動抓取 JD…"
              className="w-full border border-slate-300 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>
          <Button variant="secondary" icon={LinkIcon} loading={fetching} onClick={fetchUrl}>抓取</Button>
        </div>
        {fetchErr && <p className="text-sm text-amber-600 mb-2">{fetchErr}</p>}
        <textarea
          className="w-full border border-slate-300 rounded-lg p-3 text-sm h-32 focus:outline-none focus:ring-2 focus:ring-brand-200"
          placeholder="或直接貼上職缺 JD 文字…"
          value={jd}
          onChange={(e) => setJd(e.target.value)}
        />
        <div className="flex flex-wrap gap-2 mt-3 items-center">
          <Button onClick={() => run()} disabled={phase === "running" || !jd.trim()}
            loading={phase === "running"} icon={Sparkles}>
            開始（跑 8 個 agent）
          </Button>
          <Button variant="secondary" onClick={loadSample} disabled={phase === "running"}>載入範例 JD</Button>
          {hasDocs && (
            <>
              <Button variant={editing ? "primary" : "secondary"} icon={Pencil} onClick={toggleEdit}>
                {editing ? "完成編輯" : "編輯"}
              </Button>
              <Button variant="secondary" icon={FileDown} onClick={downloadDocx}>下載 Word</Button>
              <Button variant="secondary" icon={Printer} onClick={printDocs}>列印 / 匯出 PDF</Button>
            </>
          )}
        </div>
        {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
      </Card>

      <div className="grid lg:grid-cols-[300px_1fr] gap-6 print:block">
        <aside className="no-print">
          <AgentTrace
            done={done}
            running={phase === "running"}
            revisions={revisions}
            status={status}
            telemetry={telemetry}
            nodeErrors={nodeErrors}
          />
        </aside>
        <main className="space-y-4">
          {profileWarning && (
            <div className="border border-amber-300 bg-amber-50 rounded-xl p-3 text-sm text-amber-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />{profileWarning}
            </div>
          )}
          {phase === "approval" && (
            <Card className="no-print border-brand-200 bg-brand-50/60 p-4 flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-brand-600" />這份投遞包要核可嗎？
              </span>
              <Button size="sm" variant="primary" icon={CheckCircle2} onClick={() => decide("y")}>核可</Button>
              <Button size="sm" variant="danger" icon={RefreshCw} onClick={() => decide("n")}>退回重做</Button>
            </Card>
          )}
          {state.approved === true && (
            <div className="no-print text-sm text-emerald-700 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" />已核可
            </div>
          )}
          {state.approved === false && (
            <div className="no-print text-sm text-rose-700 flex items-center gap-1.5">
              <RefreshCw className="w-4 h-4" />已退回
            </div>
          )}

          {nodeErrors.length > 0 && (
            <div className="no-print bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
              <p className="font-medium mb-1 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />部分環節降級（已用替代內容續跑，可重試提升品質）
              </p>
              <ul className="list-disc pl-5 space-y-0.5">
                {nodeErrors.map((e, i) => <li key={i}>{e.node}：{e.message}</li>)}
              </ul>
            </div>
          )}

          {state.match_report && <MatchCard m={state.match_report} />}
          {state.company_brief && <CompanyCard c={state.company_brief} />}
          {state.tailored_resume && (
            <ResumeDoc
              r={state.tailored_resume}
              editing={editing}
              summary={edited?.resumeSummary}
              bullets={edited?.resumeBullets}
              onSummary={(v) => patch({ resumeSummary: v })}
              onBullets={(v) => patch({ resumeBullets: v })}
            />
          )}
          {state.cover_letter && (
            <CoverLetterDoc
              c={state.cover_letter}
              editing={editing}
              subject={edited?.coverSubject}
              body={edited?.coverBody}
              onSubject={(v) => patch({ coverSubject: v })}
              onBody={(v) => patch({ coverBody: v })}
            />
          )}
          {state.interview_kit && <InterviewKitDoc k={state.interview_kit} />}
          {state.critique && <CritiqueCard q={state.critique} />}

          {!hasDocs && phase !== "running" && (
            <Card className="p-2">
              <EmptyState
                icon={Network}
                title="貼上 JD 後按「開始」"
                desc="這裡會即時長出投遞包成品（客製履歷／求職信／面試準備／公司情報），左側可看 8 個 agent 的即時編排。"
              />
            </Card>
          )}
        </main>
      </div>
    </div>
  )
}
