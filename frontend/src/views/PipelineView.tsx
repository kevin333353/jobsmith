import { useEffect, useRef, useState } from "react"
import type { PipelineState, Seed, UserProfile, TelemetryEntry, Preferences } from "../types"
import { AgentTrace } from "../components/pipeline/AgentTrace"
import {
  MatchCard, CompanyCard, ResumeDoc, CoverLetterDoc, InterviewKitDoc, CritiqueCard,
} from "../components/pipeline/Documents"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { EmptyState } from "../ui/EmptyState"
import {
  Sparkles, Network, ArrowLeft, AlertTriangle, FileText, ChevronLeft, ChevronRight,
  Loader2, CheckCircle2,
} from "../ui/icons"

type Phase = "idle" | "running" | "done"
// 記住目前/最近一次背景產生，重新整理或切回分頁時接回繼續看。
const RUN_KEY = "copilot.currentRun.v1"

interface RunEvent {
  type: string
  node?: string
  data?: Partial<PipelineState>
  message?: string
  package_id?: number
  [k: string]: unknown
}

export function PipelineView(
  { seed, fallbackProfile, preferences, onBack }:
  { seed?: Seed | null; fallbackProfile?: UserProfile | null; preferences?: Preferences; onBack?: () => void },
) {
  const [jd, setJd] = useState("")
  const [manualJd, setManualJd] = useState("")
  const [phase, setPhase] = useState<Phase>("idle")
  const [status, setStatus] = useState("")
  const [done, setDone] = useState<string[]>([])
  const [state, setState] = useState<PipelineState>({})
  const [revisions, setRevisions] = useState(0)
  const [telemetry, setTelemetry] = useState<TelemetryEntry[]>([])
  const [nodeErrors, setNodeErrors] = useState<{ node: string; message: string }[]>([])
  const [profileWarning, setProfileWarning] = useState("")
  const [error, setError] = useState("")
  const [page, setPage] = useState(0)

  // 輪詢狀態：目前 thread、已收事件數、計時器 id。
  const poll = useRef<{ thread: string; since: number; timer: number | null }>(
    { thread: "", since: 0, timer: null })

  function resetView() {
    setError(""); setNodeErrors([]); setProfileWarning(""); setTelemetry([])
    setDone([]); setState({}); setRevisions(0); setPage(0)
  }

  function applyEvent(ev: RunEvent) {
    if (ev.type === "node") {
      setDone((d) => [...d, ev.node as string])
      if (ev.data) setState((s) => ({ ...s, ...ev.data }))
      if (ev.node === "critic" && ev.data?.revision_count) setRevisions(ev.data.revision_count)
    } else if (ev.type === "node_error") {
      setNodeErrors((e) => [...e, { node: ev.node as string, message: ev.message || "" }])
    } else if (ev.type === "profile_warning") {
      setProfileWarning(ev.message || "")
    } else if (ev.type === "telemetry") {
      setTelemetry((t) => [...t, ev as unknown as TelemetryEntry])
    } else if (ev.type === "done") {
      setPhase("done"); setStatus("完成 ✅")
    } else if (ev.type === "error") {
      setError(ev.message || "發生錯誤"); setPhase("done"); setStatus("")
    }
  }

  function stopPoll() {
    if (poll.current.timer) { window.clearTimeout(poll.current.timer); poll.current.timer = null }
  }

  // 輪詢某次背景產生的進度；done 或 found=false 即停。重新整理可從 since=0 重播全部。
  function startPolling(threadId: string, packageId: number) {
    stopPoll()
    poll.current = { thread: threadId, since: 0, timer: null }
    setPhase("running"); setStatus("產生中…")
    const tick = async () => {
      try {
        const r = await fetch(`/api/run/events/${threadId}?since=${poll.current.since}`)
        const d = await r.json()
        if (!d.found) { await loadFromHistory(packageId); return }  // 已清理/伺服器重啟 → 改載歷史
        const events: RunEvent[] = d.events || []
        poll.current.since += events.length
        events.forEach(applyEvent)
        if (d.done) { stopPoll(); setPhase("done"); return }
        poll.current.timer = window.setTimeout(tick, 900)
      } catch {
        poll.current.timer = window.setTimeout(tick, 1500)
      }
    }
    tick()
  }

  async function loadFromHistory(packageId: number) {
    stopPoll()
    try {
      const d = await (await fetch(`/api/history/${packageId}`)).json()
      if (d && d.package) {
        const pkg = d.package as PipelineState
        setState(pkg); if (d.jd_text) setJd(d.jd_text)
        // 已完成的包是一次載入的，沒有逐節點事件 → 依成品反推已完成節點，讓左側編排顯示綠燈而非全部待跑。
        const nd: string[] = []
        if (pkg.parsed_job) nd.push("parse")
        if (pkg.match_report) nd.push("match", "supervisor_match")
        if (pkg.company_brief) nd.push("company_research")
        if (pkg.tailored_resume) nd.push("resume_tailor")
        if (pkg.cover_letter) nd.push("cover_letter")
        if (pkg.interview_kit) nd.push("interview_prep")
        if (pkg.tailored_resume || pkg.cover_letter || pkg.interview_kit) nd.push("join")
        if (pkg.critique) nd.push("critic", "supervisor_critic", "human_gate")
        setDone(nd)
      }
    } catch { /* 忽略 */ }
    setPhase("done"); setStatus("")
  }

  // 產生投遞包（背景、射後不理）：POST /api/run → 記住 thread → 開始輪詢。
  // 完成後自動存進「我的投遞包」(待審)；離開頁面/重新整理都不中斷。
  async function run(jdText: string, profile?: UserProfile | null) {
    if (!jdText.trim()) return
    const effectiveProfile = profile ?? fallbackProfile ?? null
    resetView(); setJd(jdText); setPhase("running"); setStatus("啟動中…")
    try {
      const r = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jdText, profile: effectiveProfile, preferences: preferences ?? null }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        setError(d.error || "啟動失敗，請稍後再試。"); setPhase("idle"); return
      }
      const d = await r.json()
      localStorage.setItem(RUN_KEY, JSON.stringify({ threadId: d.thread_id, packageId: d.package_id, jd: jdText }))
      startPolling(d.thread_id, d.package_id)
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。"); setPhase("idle")
    }
  }

  // 從「自動找職缺」帶 JD 進來 → 立刻在背景產生（seed.nonce 外部訊號觸發）。
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (seed?.jd) run(seed.jd, seed.profile)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.nonce])

  // 掛載時（無 seed）接回最近一次背景產生：重新整理/切回分頁都能繼續看。
  useEffect(() => {
    if (seed?.jd) return
    try {
      const raw = localStorage.getItem(RUN_KEY)
      if (!raw) return
      const s = JSON.parse(raw)
      if (s.threadId && s.packageId) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setJd(s.jd || "")
        startPolling(s.threadId, s.packageId)
      }
    } catch { /* 忽略毀損快取 */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 卸載時停止輪詢（分頁常駐通常不卸載，保險）。
  useEffect(() => () => stopPoll(), [])

  // 成品分頁：右側一次只顯示一份（唯讀），用分頁標籤或上一頁/下一頁切換。
  const docFor = (key: string) => {
    switch (key) {
      case "match": return state.match_report ? <MatchCard m={state.match_report} /> : null
      case "company": return state.company_brief ? <CompanyCard c={state.company_brief} /> : null
      case "resume": return state.tailored_resume ? <ResumeDoc r={state.tailored_resume} /> : null
      case "cover": return state.cover_letter ? <CoverLetterDoc c={state.cover_letter} /> : null
      case "interview": return state.interview_kit ? <InterviewKitDoc k={state.interview_kit} /> : null
      case "critique": return state.critique ? <CritiqueCard q={state.critique} /> : null
      default: return null
    }
  }
  const PAGE_DEFS = [
    { key: "match", label: "匹配評分" }, { key: "company", label: "公司情報" },
    { key: "resume", label: "客製履歷" }, { key: "cover", label: "求職信" },
    { key: "interview", label: "面試準備" }, { key: "critique", label: "品管" },
  ]
  const exists: Record<string, boolean> = {
    match: !!state.match_report, company: !!state.company_brief, resume: !!state.tailored_resume,
    cover: !!state.cover_letter, interview: !!state.interview_kit, critique: !!state.critique,
  }
  const pages = PAGE_DEFS.filter((p) => exists[p.key])
  const curPage = Math.min(page, Math.max(0, pages.length - 1))
  const hasDocs = pages.length > 0
  const jdTitle = jd.split("\n").map((s) => s.trim()).find(Boolean) || "此職缺"
  const idleEmpty = phase === "idle" && !hasDocs

  return (
    <div>
      {onBack && (
        <button onClick={onBack}
          className="no-print text-sm text-brand-600 hover:text-brand-700 mb-3 inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />回職缺列表
        </button>
      )}

      {idleEmpty ? (
        // 空狀態：從「自動找職缺」按產生投遞包，或直接貼 JD 產生。
        <Card className="p-5">
          <p className="text-sm text-slate-600 mb-3">
            到「自動找職缺」對某個職缺按「產生投遞包」，這裡會即時長出成品。
            產生在背景進行，<strong>離開或重新整理都不會中斷</strong>，完成後自動存進「我的投遞包」（待審）。
            也可直接貼 JD 產生：
          </p>
          <textarea
            className="w-full border border-slate-300 rounded-lg p-3 text-sm h-32 focus:outline-none focus:ring-2 focus:ring-brand-200"
            placeholder="貼上職缺 JD 文字…" value={manualJd} onChange={(e) => setManualJd(e.target.value)} />
          <div className="mt-3">
            <Button icon={Sparkles} disabled={!manualJd.trim()} onClick={() => run(manualJd)}>產生投遞包</Button>
          </div>
          {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
        </Card>
      ) : (
        <div className="grid lg:grid-cols-[300px_1fr] gap-6">
          <aside className="no-print">
            <AgentTrace done={done} running={phase === "running"} revisions={revisions}
              status={status} telemetry={telemetry} nodeErrors={nodeErrors} />
          </aside>
          <main className="space-y-4">
            <div className="no-print flex items-center gap-2 flex-wrap">
              <FileText className="w-4 h-4 text-brand-600 shrink-0" />
              <span className="font-medium text-slate-800 truncate" title={jdTitle}>{jdTitle}</span>
              {phase === "running" && (
                <span className="text-sm text-brand-600 inline-flex items-center gap-1">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />產生中…
                </span>
              )}
              {phase === "done" && !error && (
                <span className="text-sm text-emerald-600 inline-flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />已存入「我的投遞包」（待審）
                </span>
              )}
            </div>

            {profileWarning && (
              <div className="border border-amber-300 bg-amber-50 rounded-xl p-3 text-sm text-amber-800 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />{profileWarning}
              </div>
            )}
            {error && <p className="text-sm text-rose-600">{error}</p>}
            {nodeErrors.length > 0 && (
              <div className="no-print bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
                <p className="font-medium mb-1 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4" />部分環節降級（已用替代內容續跑）
                </p>
                <ul className="list-disc pl-5 space-y-0.5">
                  {nodeErrors.map((e, i) => <li key={i}>{e.node}：{e.message}</li>)}
                </ul>
              </div>
            )}

            {hasDocs ? (
              <Card className="p-4">
                <div className="flex flex-wrap gap-1.5 border-b border-slate-200 pb-2 mb-3">
                  {pages.map((p, i) => (
                    <button key={p.key} type="button" onClick={() => setPage(i)}
                      aria-current={i === curPage ? "page" : undefined}
                      className={`px-3 py-1.5 rounded-lg text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                        i === curPage ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
                      }`}>{p.label}</button>
                  ))}
                </div>
                <div className="max-h-[62vh] overflow-auto pr-1">{docFor(pages[curPage].key)}</div>
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-200">
                  <Button variant="secondary" size="sm" icon={ChevronLeft}
                    disabled={curPage <= 0} onClick={() => setPage(curPage - 1)}>上一頁</Button>
                  <span className="text-sm text-slate-500">{curPage + 1} / {pages.length}</span>
                  <Button variant="secondary" size="sm"
                    disabled={curPage >= pages.length - 1} onClick={() => setPage(curPage + 1)}>
                    下一頁<ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </Card>
            ) : phase === "running" ? (
              <Card className="p-2">
                <EmptyState icon={Network} title="正在產生投遞包…"
                  desc="左側可看多 agent 的即時編排，成品會逐步出現。離開或重新整理都不會中斷。" />
              </Card>
            ) : null}
          </main>
        </div>
      )}
    </div>
  )
}
