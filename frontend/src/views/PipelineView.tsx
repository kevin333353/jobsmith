import { useEffect, useRef, useState } from "react"
import type {
  CandidateProfile,
  GenerationOptions,
  JobMatch,
  PipelineState,
  Seed,
  UserProfile,
  TelemetryEntry,
  Preferences,
} from "../types"
import { AgentTrace } from "../components/pipeline/AgentTrace"
import { GenerationOptionsPanel } from "../components/pipeline/GenerationOptionsPanel"
import { CandidateProfileManager } from "../components/CandidateProfileManager"
import { makeCandidateProfile, profileDisplayName } from "../lib/profiles"
import {
  QUICK_GENERATION,
  generationPayload,
  normalizeGenerationOptions,
  optionsFromPipelineState,
  searchAnalysisPayload,
} from "../lib/packageGeneration"
import {
  MatchCard, CompanyCard, ResumeDoc, CoverLetterDoc, InterviewKitDoc, CritiqueCard,
} from "../components/pipeline/Documents"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { EmptyState } from "../ui/EmptyState"
import {
  Sparkles, Network, ArrowLeft, AlertTriangle, FileText, ChevronLeft, ChevronRight,
  Loader2, CheckCircle2, XCircle,
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
  {
    seed, activeProfile, profiles, preferences, watch, onBack, onSelectProfile,
    onSaveActiveProfile, onUpdateActiveProfile, onDeleteProfile, onClearActiveProfile,
  }:
  {
    seed?: Seed | null; activeProfile?: CandidateProfile | null; profiles: CandidateProfile[]; preferences?: Preferences
    watch?: { threadId: string; packageId: number; title?: string; nonce: number } | null
    onBack?: () => void
    onSelectProfile: (p: CandidateProfile | null) => void
    onSaveActiveProfile: (label?: string) => void | Promise<void>
    onUpdateActiveProfile: (profile: UserProfile) => void
    onDeleteProfile: (id: string) => void
    onClearActiveProfile: () => void
  },
) {
  const [jd, setJd] = useState("")
  const [manualJd, setManualJd] = useState("")
  const [pendingJd, setPendingJd] = useState("")
  const [pendingMatch, setPendingMatch] = useState<JobMatch | null>(null)
  const [phase, setPhase] = useState<Phase>("idle")
  const [status, setStatus] = useState("")
  const [done, setDone] = useState<string[]>([])
  const [state, setState] = useState<PipelineState>({})
  const [generationOptions, setGenerationOptions] = useState<GenerationOptions>(
    () => ({ ...QUICK_GENERATION, artifactTargets: [...QUICK_GENERATION.artifactTargets] }),
  )
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
    setDone([]); setState({}); setPage(0)
  }

  function applyEvent(ev: RunEvent) {
    if (ev.type === "config" && ev.data) {
      setGenerationOptions(optionsFromPipelineState(ev.data))
      setState((current) => ({ ...current, ...ev.data }))
    } else if (ev.type === "node") {
      setDone((d) => [...d, ev.node as string])
      if (ev.data) setState((s) => ({ ...s, ...ev.data }))
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
    } else if (ev.type === "stopped") {
      setPhase("done"); setStatus(ev.message || "已停止任務")
    }
  }

  function stopPoll() {
    if (poll.current.timer) { window.clearTimeout(poll.current.timer); poll.current.timer = null }
  }

  async function stopRun() {
    const threadId = poll.current.thread
    stopPoll()
    localStorage.removeItem(RUN_KEY)
    setPhase("done")
    setStatus("已停止任務")
    if (!threadId) return
    try {
      const r = await fetch(`/api/run/${threadId}/stop`, { method: "POST" })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        setError(d.error || "停止任務失敗，請稍後再試。")
      }
    } catch {
      setError("停止任務失敗，請確認伺服器是否仍在執行。")
    }
  }

  // 輪詢某次背景產生的進度；done 或 found=false 即停。重新整理可從 since=0 重播全部。
  function startPolling(threadId: string, packageId: number) {
    stopPoll()
    poll.current = { thread: threadId, since: 0, timer: null }
    setPhase("running"); setStatus("產生中…")
    let failures = 0
    const tick = async () => {
      try {
        const r = await fetch(`/api/run/events/${threadId}?since=${poll.current.since}`)
        const d = await r.json()
        failures = 0
        if (!d.found) { await loadFromHistory(packageId); return }  // 已清理/伺服器重啟 → 改載歷史
        const events: RunEvent[] = d.events || []
        poll.current.since += events.length
        events.forEach(applyEvent)
        if (d.done) { stopPoll(); setPhase("done"); return }
        poll.current.timer = window.setTimeout(tick, 900)
      } catch {
        failures += 1
        if (failures >= 2) setStatus("重新連線中...")
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
        setState(pkg)
        setGenerationOptions(optionsFromPipelineState(pkg))
        if (d.jd_text) setJd(d.jd_text)
        // 已完成的包是一次載入的，沒有逐節點事件 → 依成品反推已完成節點，讓左側編排顯示綠燈而非全部待跑。
        const nd: string[] = []
        if (pkg.parsed_job) nd.push("parse")
        if (pkg.match_report) nd.push("match", "supervisor_match")
        if (pkg.company_brief) nd.push("company_research")
        if (pkg.tailored_resume) nd.push("resume_tailor")
        if (pkg.cover_letter) nd.push("cover_letter")
        if (pkg.interview_kit) nd.push("interview_prep")
        if (pkg.tailored_resume || pkg.cover_letter || pkg.interview_kit) nd.push("join")
        if (pkg.critique) nd.push("critic")
        if (pkg.tailored_resume || pkg.cover_letter || pkg.interview_kit) nd.push("human_gate")
        setDone(nd)
      }
    } catch { /* 忽略 */ }
    setPhase("done"); setStatus("")
  }

  // 產生投遞包（背景、射後不理）：POST /api/run → 記住 thread → 開始輪詢。
  // 完成後自動存進「我的投遞包」(待審)；離開頁面/重新整理都不中斷。
  async function run(
    jdText: string,
    profile: UserProfile | null,
    options: GenerationOptions,
    searchMatch?: JobMatch | null,
  ) {
    if (!jdText.trim()) return
    const effectiveProfile = profile ?? null
    const normalized = normalizeGenerationOptions(options)
    const payload = generationPayload(normalized)
    resetView(); setJd(jdText); setPhase("running"); setStatus("啟動中…")
    setGenerationOptions(normalized)
    setState(payload)
    try {
      const r = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jd_text: jdText,
          profile: effectiveProfile,
          preferences: preferences ?? null,
          ...payload,
          ...searchAnalysisPayload(jdText, searchMatch),
        }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        setError(d.error || "啟動失敗，請稍後再試。"); setPhase("idle"); return
      }
      const d = await r.json()
      localStorage.setItem(RUN_KEY, JSON.stringify({
        threadId: d.thread_id,
        packageId: d.package_id,
        jd: jdText,
        options: normalized,
      }))
      startPolling(d.thread_id, d.package_id)
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。"); setPhase("idle")
    }
  }

  // 從「自動找職缺」帶 JD 進來 → 先進產出前確認，避免沿用錯誤 Profile。
  useEffect(() => {
    if (!seed?.jd) return
    const timer = window.setTimeout(() => {
      resetView()
      setPendingJd(seed.jd)
      setPendingMatch(seed.match || null)
      setGenerationOptions({ ...QUICK_GENERATION, artifactTargets: [...QUICK_GENERATION.artifactTargets] })
      setJd(""); setManualJd(""); setPhase("idle"); setStatus("")
    }, 0)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.nonce])

  // 從「我的投遞包」點進行中的那筆 → 接回該背景產生看即時進度（watch.nonce 外部訊號觸發）。
  useEffect(() => {
    if (!watch?.threadId) return
    const timer = window.setTimeout(() => {
      resetView(); setPendingJd(""); setPendingMatch(null); setJd(watch.title || "")
      setGenerationOptions({ ...QUICK_GENERATION, artifactTargets: [...QUICK_GENERATION.artifactTargets] })
      localStorage.setItem(RUN_KEY, JSON.stringify(
        { threadId: watch.threadId, packageId: watch.packageId, jd: watch.title || "" }))
      startPolling(watch.threadId, watch.packageId)
    }, 0)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watch?.nonce])

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
        if (s.options) setGenerationOptions(normalizeGenerationOptions(s.options))
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
      case "critique": return state.critique
        ? <CritiqueCard q={state.critique} targets={generationOptions.artifactTargets} />
        : null
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
  const pendingTitle = pendingJd.split("\n").map((s) => s.trim()).find(Boolean) || "此職缺"
  const idleConfirm = phase === "idle" && !hasDocs && Boolean(pendingJd.trim())
  const idleEmpty = phase === "idle" && !hasDocs && !pendingJd.trim()
  const seedProfile = seed?.profile && !activeProfile
    ? makeCandidateProfile(seed.profile, {
        label: profileDisplayName(seed.profile),
        resumeLabel: "本次帶入履歷",
        saved: false,
      })
    : null
  const confirmProfile = activeProfile || seedProfile

  function confirmRun(useProfile: boolean) {
    const text = pendingJd.trim() ? pendingJd : manualJd
    const searchMatch = pendingMatch
    setPendingJd("")
    setPendingMatch(null)
    void run(
      text,
      useProfile ? confirmProfile?.profile ?? null : null,
      generationOptions,
      searchMatch,
    )
  }

  return (
    <div>
      {onBack && (
        <button onClick={onBack}
          className="no-print text-sm text-brand-600 hover:text-brand-700 mb-3 inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />回職缺列表
        </button>
      )}

      {idleConfirm ? (
        <Card className="p-5">
          <div className="mb-4">
            <p className="text-xs text-slate-400 mb-1">產出前確認</p>
            <h2 className="font-semibold text-lg text-slate-900 truncate" title={pendingTitle}>{pendingTitle}</h2>
            <p className="text-sm text-slate-500 mt-1">
              確認候選人 Profile，再選這次真正需要的文件；未勾選的環節不會呼叫 AI。
            </p>
          </div>
          <CandidateProfileManager
            compact
            profiles={profiles}
            activeProfile={confirmProfile || null}
            preferences={preferences}
            onSelectProfile={onSelectProfile}
            onSaveActiveProfile={activeProfile ? onSaveActiveProfile : undefined}
            onUpdateActiveProfile={activeProfile ? onUpdateActiveProfile : undefined}
            onDeleteProfile={onDeleteProfile}
            onClearActiveProfile={onClearActiveProfile}
          />
          <GenerationOptionsPanel
            value={generationOptions}
            onChange={(next) => setGenerationOptions(normalizeGenerationOptions(next))}
            reusesSearchAnalysis={Boolean(pendingMatch)}
          />
          <div className="mt-5 flex flex-wrap gap-2">
            <Button icon={Sparkles} disabled={!confirmProfile} onClick={() => confirmRun(true)}>
              使用此 Profile 開始
            </Button>
            <Button variant="secondary" onClick={() => confirmRun(false)}>
              使用示範 Profile
            </Button>
            <Button variant="ghost" onClick={() => { setPendingJd(""); setPendingMatch(null) }}>取消</Button>
          </div>
        </Card>
      ) : idleEmpty ? (
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
            <Button icon={Sparkles} disabled={!manualJd.trim()} onClick={() => {
              setPendingMatch(null)
              setGenerationOptions({
                ...QUICK_GENERATION,
                artifactTargets: [...QUICK_GENERATION.artifactTargets],
              })
              setPendingJd(manualJd)
            }}>
              確認生成設定
            </Button>
          </div>
          {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
        </Card>
      ) : (
        <div className="grid lg:grid-cols-[300px_1fr] gap-6">
          <aside className="no-print">
            <AgentTrace done={done} running={phase === "running"} options={generationOptions}
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
              {phase === "running" && (
                <Button variant="secondary" size="sm" icon={XCircle} onClick={() => void stopRun()}>
                  停止任務
                </Button>
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
                {/* 分頁標籤 + 上一頁/下一頁都放頂端，永遠可點，不必往下滑 */}
                <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-2 mb-3">
                  <div className="flex flex-wrap gap-1.5">
                    {pages.map((p, i) => (
                      <button key={p.key} type="button" onClick={() => setPage(i)}
                        aria-current={i === curPage ? "page" : undefined}
                        className={`px-3 py-1.5 rounded-lg text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                          i === curPage ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
                        }`}>{p.label}</button>
                    ))}
                  </div>
                  <div className="ml-auto flex items-center gap-2 shrink-0">
                    <Button variant="secondary" size="sm" icon={ChevronLeft}
                      disabled={curPage <= 0} onClick={() => setPage(curPage - 1)}>上一頁</Button>
                    <span className="text-sm text-slate-500">{curPage + 1} / {pages.length}</span>
                    <Button variant="secondary" size="sm"
                      disabled={curPage >= pages.length - 1} onClick={() => setPage(curPage + 1)}>
                      下一頁<ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                {/* key=當前頁 → 切頁時內容捲軸回到頂端 */}
                <div key={pages[curPage].key} className="max-h-[68vh] overflow-auto pr-1">
                  {docFor(pages[curPage].key)}
                </div>
              </Card>
            ) : phase === "running" ? (
              <Card className="p-2">
                <EmptyState icon={Network} title="正在產生所選文件…"
                  desc="左側只顯示這次會執行的步驟；離開或重新整理都不會中斷。" />
              </Card>
            ) : null}
          </main>
        </div>
      )}
    </div>
  )
}
