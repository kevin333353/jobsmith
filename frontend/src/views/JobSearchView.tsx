import { useEffect, useId, useMemo, useRef, useState } from "react"
import type { ChangeEvent, KeyboardEvent as ReactKeyboardEvent } from "react"
import type {
  CandidateProfile,
  JobMatch,
  JobsAutoEvent,
  SkillGapReport,
  UserProfile,
} from "../types"
import { readSSE } from "../sse"
import { SAMPLE_RESUME } from "../sampleResume"
import { resolveJd } from "../lib/resolveJd"
import { newTaskId, stopTask } from "../lib/taskControl"
import { profileDisplayName, profileSummary } from "../lib/profiles"
import { EXPERIENCE_FILTER_OPTIONS } from "../components/jobs/experience"
import { JobList } from "../components/jobs/JobList"
import { DiscoveryInsights } from "../components/jobs/DiscoveryInsights"
import { ResultRefinementBar } from "../components/jobs/ResultRefinementBar"
import { TargetRoleEditor } from "../components/jobs/TargetRoleEditor"
import {
  createEmptyResultRefinement,
  filterJobMatches,
  normalizeResultRefinement,
  type ResultRefinementState,
} from "../components/jobs/resultRefinement"
import { appendSalaryFilter, type SalaryUnit } from "../components/jobs/salaryFilter"
import {
  appendWorkModeFilter,
  normalizeWorkModeFilters,
  WORK_MODE_OPTIONS,
  type WorkModeFilter,
} from "../lib/workMode"
import { SRC_LABEL } from "../lib/sources"
import {
  DEFAULT_JOB_SEARCH_MODE,
  normalizeJobSearchMode,
  profileTargetRoles,
  type JobSearchMode,
} from "../lib/localDiscovery"
import { describeSearchScope } from "../lib/searchScope"
import { shouldReuseResumePreview } from "../lib/publicWeb"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Badge } from "../ui/Badge"
import { Skeleton } from "../ui/Skeleton"
import { EmptyState } from "../ui/EmptyState"
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Coins,
  ExternalLink,
  FileText,
  Laptop,
  Layers,
  Loader2,
  MapPin,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Timer,
  Upload,
  UserRound,
  X,
  XCircle,
} from "../ui/icons"

const SNAP_KEY = "copilot.jobsearch.v1"  // 上次搜尋結果快取（重新整理/重開沿用）
const WEB_SNAP_KEY = "jobsmith.web.jobsearch.v1"

type SourceStat = { source: string; count: number; blocked: boolean }
// 串流累積容器（完成後整包存進搜尋紀錄）；state 更新非同步，存檔讀這裡的即時值。
type SearchAcc = {
  jobs: JobMatch[]; companyJobs: JobMatch[]
  queries: string[]; sources: SourceStat[]; linkedin: string; fallback: boolean
  profile: UserProfile | null; skillGap: SkillGapReport | null; searchMode: JobSearchMode
}
// 同分時以 url 決定先後，讓分批串流到達的順序不影響最終排序（可重現）。
const sortByFit = (arr: JobMatch[]) =>
  [...arr].sort((a, b) => b.fit_score - a.fit_score || (a.job.url < b.job.url ? -1 : a.job.url > b.job.url ? 1 : 0))

function profileWithoutResumeText(profile: UserProfile | null): UserProfile | null {
  if (!profile) return null
  const compact = { ...profile }
  delete compact.raw_text
  return compact
}

// 搜尋地點（縣市，對應後端 app/sources/regions.py）：搜尋前選定、所有來源一致生效；不選＝全台。
const COUNTIES = [
  "台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市",
  "基隆市", "新竹縣市", "苗栗縣", "彰化縣", "南投縣", "雲林縣",
  "嘉義縣市", "屏東縣", "宜蘭縣", "花蓮縣", "台東縣",
]

function mergeSource(arr: SourceStat[], ev: { source: string; count: number; blocked: boolean }): SourceStat[] {
  const idx = arr.findIndex((x) => x.source === ev.source)
  if (idx < 0) return [...arr, { source: ev.source, count: ev.count, blocked: ev.blocked }]
  const copy = [...arr]
  copy[idx] = { source: ev.source, count: copy[idx].count + ev.count, blocked: copy[idx].blocked && ev.blocked }
  return copy
}

export function JobSearchView(
  {
    onPick,
    onProfile,
    activeProfile,
    formOpen,
    setFormOpen,
    onHasResults,
    publicWeb = false,
    maxSearchPages = 5,
  }:
  {
    onPick: (jd: string, profile?: UserProfile | null, match?: JobMatch | null) => void
    onProfile?: (p: UserProfile, meta?: { label?: string; resumeLabel?: string }) => void
    activeProfile?: CandidateProfile | null
    formOpen: boolean                    // 搜尋表單是否展開（提升到 App，收合鈕放右上角）
    setFormOpen: (v: boolean) => void
    onHasResults?: (v: boolean) => void  // 回報是否已有結果，App 才知道要不要顯示收合鈕
    publicWeb?: boolean
    maxSearchPages?: number
  },
) {
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [status, setStatus] = useState("")
  const [queries, setQueries] = useState<string[]>([])
  const [sources, setSources] = useState<SourceStat[]>([])
  const [jobs, setJobs] = useState<JobMatch[]>([])
  const [companyJobs, setCompanyJobs] = useState<JobMatch[]>([])
  const [rankTotal, setRankTotal] = useState(0)
  const [regions, setRegions] = useState<string[]>([])  // 搜尋地點（縣市 key；空 = 全台）
  const [workModes, setWorkModes] = useState<WorkModeFilter[]>([])
  const [includeInferredWorkMode, setIncludeInferredWorkMode] = useState(false)
  const [linkedin, setLinkedin] = useState("")
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [previewProfile, setPreviewProfile] = useState<UserProfile | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewError, setPreviewError] = useState("")
  const [targetRoles, setTargetRoles] = useState<string[]>([])
  const [skillGap, setSkillGap] = useState<SkillGapReport | null>(null)
  const [searchMode, setSearchMode] = useState<JobSearchMode>(
    publicWeb ? "local" : DEFAULT_JOB_SEARCH_MODE,
  )
  const [resultMode, setResultMode] = useState<JobSearchMode>(
    publicWeb ? "local" : DEFAULT_JOB_SEARCH_MODE,
  )
  const [blockedNote, setBlockedNote] = useState("")
  const [fallback, setFallback] = useState(false)
  const [error, setError] = useState("")
  const [companies, setCompanies] = useState<string[]>([])
  const [companyInput, setCompanyInput] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [resumeTextOpen, setResumeTextOpen] = useState(false)
  const [scopeOpen, setScopeOpen] = useState(false)
  const [allRegionsOpen, setAllRegionsOpen] = useState(false)
  const [searchedCompanies, setSearchedCompanies] = useState<string[]>([])
  const [pages, setPages] = useState(2)  // 每個來源抓幾頁（越多越全、但越慢）
  const [maxExperienceYears, setMaxExperienceYears] = useState("")
  const [salaryUnit, setSalaryUnit] = useState<SalaryUnit>("monthly")
  const [minSalary, setMinSalary] = useState("")
  const [maxSalary, setMaxSalary] = useState("")
  const [includeUnknownSalary, setIncludeUnknownSalary] = useState(true)
  const [resultRefinement, setResultRefinement] = useState<ResultRefinementState>(
    createEmptyResultRefinement,
  )

  const abortRef = useRef<AbortController | null>(null)  // 取消上一個未完成的搜尋
  const previewSeqRef = useRef(0)
  const targetRolesEditedRef = useRef(false)
  const taskIdRef = useRef("")
  const stoppingRef = useRef(false)
  const scopePanelId = useId()

  // 還原上次搜尋結果：重新整理 / 重開不必重找（僅開啟時還原一次，是 effect 正當用途）。
  useEffect(() => {
    try {
      const raw = localStorage.getItem(publicWeb ? WEB_SNAP_KEY : SNAP_KEY)
      if (!raw) return
      const s = JSON.parse(raw)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (!publicWeb && typeof s.text === "string") setText(s.text)
      if (Array.isArray(s.companies)) setCompanies(s.companies)
      if (Array.isArray(s.jobs)) setJobs(s.jobs)
      if (Array.isArray(s.companyJobs)) setCompanyJobs(s.companyJobs)
      if (Array.isArray(s.queries)) setQueries(s.queries)
      if (Array.isArray(s.sources)) setSources(s.sources)
      if (typeof s.linkedin === "string") setLinkedin(s.linkedin)
      if (typeof s.fallback === "boolean") setFallback(s.fallback)
      if (Array.isArray(s.searchedCompanies)) setSearchedCompanies(s.searchedCompanies)
      if (typeof s.pages === "number") setPages(Math.min(s.pages, maxSearchPages))
      if (typeof s.maxExperienceYears === "string") setMaxExperienceYears(s.maxExperienceYears)
      if (s.salaryUnit === "monthly" || s.salaryUnit === "annual") setSalaryUnit(s.salaryUnit)
      if (typeof s.minSalary === "string") setMinSalary(s.minSalary)
      if (typeof s.maxSalary === "string") setMaxSalary(s.maxSalary)
      if (typeof s.includeUnknownSalary === "boolean") setIncludeUnknownSalary(s.includeUnknownSalary)
      if (Array.isArray(s.regions)) setRegions(s.regions)
      setWorkModes(normalizeWorkModeFilters(s.workModes))
      if (typeof s.includeInferredWorkMode === "boolean") {
        setIncludeInferredWorkMode(s.includeInferredWorkMode)
      }
      if (Array.isArray(s.targetRoles)) {
        const restoredRoles = s.targetRoles.filter((role: unknown) => typeof role === "string")
        setTargetRoles(restoredRoles)
        targetRolesEditedRef.current = restoredRoles.length > 0
      }
      setSearchMode(publicWeb ? "local" : normalizeJobSearchMode(s.searchMode))
      setResultMode(publicWeb ? "local" : normalizeJobSearchMode(s.resultMode ?? s.searchMode))
      if (s.skillGap && typeof s.skillGap === "object") {
        setSkillGap(s.skillGap as SkillGapReport)
      }
      setResultRefinement(normalizeResultRefinement(s.resultRefinement))
      if (s.profile) setProfile(s.profile as UserProfile)
      if (Array.isArray(s.jobs) && s.jobs.length) { setDone(true); setFormOpen(false) }
      else if (Array.isArray(s.companyJobs) && s.companyJobs.length) { setDone(true); setFormOpen(false) }
    } catch { /* 忽略毀損快取 */ }
    // 僅開啟時還原一次；onProfile 為穩定的 setState，不需列入依賴。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 履歷一選好就用本機規則做輕量預覽，讓使用者能在真正搜尋前確認目標職稱。
  useEffect(() => {
    const trimmedText = text.trim()
    if (!formOpen || (!file && trimmedText.length < 20)) return

    const sequence = ++previewSeqRef.current
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setPreviewBusy(true)
      setPreviewError("")
      const form = new FormData()
      if (file) form.append("file", file)
      else form.append("resume_text", trimmedText)

      try {
        const response = await fetch("/api/resume/preview", {
          method: "POST",
          body: form,
          signal: controller.signal,
        })
        const payload = await response.json() as { profile?: UserProfile; error?: string }
        if (!response.ok || !payload.profile) {
          throw new Error(payload.error || "無法辨識履歷")
        }
        if (sequence !== previewSeqRef.current) return
        setPreviewProfile(payload.profile)
        const detectedRoles = profileTargetRoles(payload.profile)
        if (!targetRolesEditedRef.current) setTargetRoles(detectedRoles)
      } catch (previewFailure) {
        if ((previewFailure as Error)?.name === "AbortError") return
        if (sequence !== previewSeqRef.current) return
        setPreviewError((previewFailure as Error)?.message || "無法辨識履歷")
      } finally {
        if (sequence === previewSeqRef.current) setPreviewBusy(false)
      }
    }, file ? 0 : 450)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [file, formOpen, text])

  useEffect(() => {
    if (!done) return
    try {
      const snapshot: Record<string, unknown> = {
        companies, jobs, companyJobs, queries, sources,
        linkedin, fallback, searchedCompanies,
        profile: publicWeb ? profileWithoutResumeText(profile) : profile,
        pages: Math.min(pages, maxSearchPages), regions, maxExperienceYears,
        salaryUnit, minSalary, maxSalary, includeUnknownSalary, workModes, includeInferredWorkMode,
        searchMode: publicWeb ? "local" : searchMode,
        resultMode: publicWeb ? "local" : resultMode,
        skillGap, resultRefinement, targetRoles,
      }
      if (!publicWeb) snapshot.text = text
      localStorage.setItem(publicWeb ? WEB_SNAP_KEY : SNAP_KEY, JSON.stringify(snapshot))
    } catch { /* localStorage 不可用/已滿則略過 */ }
  }, [done, jobs, companyJobs, queries, sources, linkedin, fallback,
      searchedCompanies, profile, text, companies, pages, regions, maxExperienceYears,
      salaryUnit, minSalary, maxSalary, includeUnknownSalary, workModes, includeInferredWorkMode,
      searchMode, resultMode, skillGap, resultRefinement, targetRoles, publicWeb, maxSearchPages])

  // 回報是否已有結果，App 才知道要不要在右上角顯示「收合搜尋條件」鈕。
  useEffect(() => {
    onHasResults?.(jobs.length > 0 || companyJobs.length > 0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.length, companyJobs.length])

  function addCompany(name: string) {
    const n = name.trim()
    if (!n) return
    setCompanies((c) => (c.includes(n) ? c : [...c, n]))
    setCompanyInput("")
  }
  function removeCompany(name: string) {
    setCompanies((c) => c.filter((x) => x !== name))
  }
  function onCompanyKey(e: ReactKeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === "," || e.key === "，" || e.key === "、") {
      e.preventDefault(); addCompany(companyInput)
    } else if (e.key === "Backspace" && !companyInput && companies.length) {
      setCompanies((c) => c.slice(0, -1))
    }
  }
  function toggleRegion(k: string) {
    setRegions((rs) => (rs.includes(k) ? rs.filter((x) => x !== k) : [...rs, k]))
  }
  function toggleWorkMode(mode: WorkModeFilter) {
    setWorkModes((modes) => (
      modes.includes(mode) ? modes.filter((m) => m !== mode) : [...modes, mode]
    ))
  }
  function resetResumeRecognition() {
    previewSeqRef.current += 1
    targetRolesEditedRef.current = false
    setPreviewProfile(null)
    setPreviewBusy(false)
    setPreviewError("")
    setTargetRoles([])
  }
  function changeTargetRoles(roles: string[]) {
    targetRolesEditedRef.current = true
    setTargetRoles(roles)
  }
  function changeResumeText(next: string) {
    if (!text.trim() || !next.trim()) resetResumeRecognition()
    setText(next)
  }
  function loadSampleResume() {
    resetResumeRecognition()
    setFile(null)
    setText(SAMPLE_RESUME)
    setResumeTextOpen(true)
    setError("")
  }
  function removeResumeFile() {
    resetResumeRecognition()
    setFile(null)
  }

  async function saveSearch(acc: SearchAcc, cs: string[]) {
    if (publicWeb) return
    if (!acc.jobs.length && !acc.companyJobs.length) return
    const name = (acc.profile && (acc.profile as Record<string, unknown>).name) || ""
    const label = [name || "搜尋", acc.queries[0] || ""].filter(Boolean).join(" · ")
    try {
      await fetch("/api/searches", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label, profile: acc.profile,
          payload: {
            jobs: acc.jobs, companyJobs: acc.companyJobs,
            queries: acc.queries, sources: acc.sources, searchedCompanies: cs,
            linkedin: acc.linkedin, fallback: acc.fallback,
            workModes, includeInferredWorkMode,
            searchMode: acc.searchMode, skillGap: acc.skillGap, targetRoles,
          },
        }),
      })
    } catch { /* 存檔失敗不影響使用 */ }
  }

  function appendSearchOptions(form: FormData) {
    form.append("search_mode", publicWeb ? "local" : searchMode)
    if (targetRoles.length) form.append("target_roles", targetRoles.join("\n"))
    form.append("pages", String(Math.min(pages, maxSearchPages)))
    if (regions.length) form.append("region", regions.join(","))
    if (maxExperienceYears) form.append("max_experience_years", maxExperienceYears)
    appendSalaryFilter(form, {
      unit: salaryUnit,
      min: minSalary,
      max: maxSalary,
      includeUnknown: includeUnknownSalary,
    })
    appendWorkModeFilter(form, workModes, includeInferredWorkMode)
  }

  async function go(
    form: FormData,
    opts: { resumeLabel?: string; updateActiveProfile?: boolean; initialStatus?: string } = {},
  ) {
    const trailing = companyInput.trim()
    const resumeLabel = opts.resumeLabel || (file ? file.name : "貼上的履歷")
    const cs = trailing ? (companies.includes(trailing) ? companies : [...companies, trailing]) : companies
    if (trailing) { setCompanies(cs); setCompanyInput("") }
    if (cs.length) form.append("companies", cs.join(","))
    setSearchedCompanies(cs)

    if (taskIdRef.current) void stopTask(taskIdRef.current).catch(() => undefined)
    abortRef.current?.abort()  // 取消上一個還沒跑完的搜尋，避免兩條串流交錯進同一個 acc
    const ctrl = new AbortController()
    const taskId = newTaskId("job-search")
    form.append("task_id", taskId)
    abortRef.current = ctrl
    taskIdRef.current = taskId
    stoppingRef.current = false

    setBusy(true); setDone(false); setError(""); setJobs([]); setCompanyJobs([]); setQueries([]); setSources([])
    setResultRefinement(createEmptyResultRefinement())
    setLinkedin(""); setProfile(null); setSkillGap(null); setBlockedNote(""); setFallback(false); setRankTotal(0)
    setResultMode(publicWeb ? "local" : searchMode)
    setStatus(opts.initialStatus || "上傳中…")
    // 串流累積（供完成後存檔；state 更新非同步，存檔讀這裡的即時值）。
    const acc: SearchAcc = {
      jobs: [],
      companyJobs: [],
      queries: [],
      sources: [],
      linkedin: "",
      fallback: false,
      profile: null,
      skillGap: null,
      searchMode: publicWeb ? "local" : searchMode,
    }
    let hadError = false
    try {
      const resp = await fetch("/api/jobs/auto", { method: "POST", body: form, signal: ctrl.signal })
      await readSSE(resp, (ev: JobsAutoEvent) => {
        if (ev.type === "progress") setStatus(ev.message)
        else if (ev.type === "profile") {
          acc.profile = ev.data
          setProfile(ev.data as UserProfile)
          if (opts.updateActiveProfile !== false) {
            onProfile?.(ev.data as UserProfile, { resumeLabel })
          }
        }
        else if (ev.type === "queries") { acc.queries = ev.queries; setQueries(ev.queries) }
        else if (ev.type === "skill_gap") { acc.skillGap = ev.data; setSkillGap(ev.data) }
        else if (ev.type === "source") { acc.sources = mergeSource(acc.sources, ev); setSources((s) => mergeSource(s, ev)) }
        else if (ev.type === "all_blocked") setBlockedNote(ev.message)
        else if (ev.type === "rank_start") { acc.fallback = Boolean(ev.fallback); setFallback(Boolean(ev.fallback)); setRankTotal(ev.total || 0); acc.jobs = []; setJobs([]) }
        else if (ev.type === "ranked_batch") {
          acc.jobs = sortByFit([...acc.jobs, ...(ev.data as JobMatch[])])
          setJobs(acc.jobs)
        }
        else if (ev.type === "company_jobs") { acc.companyJobs = sortByFit(ev.data as JobMatch[]); setCompanyJobs(acc.companyJobs) }
        else if (ev.type === "linkedin") { acc.linkedin = ev.url; setLinkedin(ev.url) }
        else if (ev.type === "stopped") { stoppingRef.current = true; hadError = true; setStatus(ev.message || "已停止搜尋") }
        else if (ev.type === "error") { hadError = true; setError(ev.message) }
        else if (ev.type === "done") setDone(true)
      })
      if (!hadError && (acc.jobs.length || acc.companyJobs.length)) {
        await saveSearch(acc, cs)  // 自動存進「搜尋紀錄」
      }
      if (acc.jobs.length || acc.companyJobs.length) setFormOpen(false)  // 有結果就收合表單、凸顯職缺列表
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return  // 被停止或新搜尋取消 → 靜默
      setError("連線發生問題，請確認伺服器是否啟動。")
    } finally {
      if (abortRef.current === ctrl) {
        setBusy(false)
        if (!stoppingRef.current) setStatus("")
        abortRef.current = null
        taskIdRef.current = ""
        stoppingRef.current = false
      }  // 僅當前搜尋才收尾
    }
  }

  async function stopSearch() {
    stoppingRef.current = true
    setStatus("正在停止搜尋…")
    try {
      await stopTask(taskIdRef.current)
    } catch {
      // 停止端點失敗時仍中止前端串流，避免使用者被卡在等待狀態。
    } finally {
      abortRef.current?.abort()
      setBusy(false)
      setStatus("已停止搜尋")
    }
  }

  function onStart() {
    const form = new FormData()
    let options: { resumeLabel?: string; updateActiveProfile?: boolean; initialStatus?: string } = {}
    if (shouldReuseResumePreview(publicWeb, Boolean(file), Boolean(previewProfile), previewBusy)) {
      // Public Web needs only the compact local profile after preview. Avoid uploading
      // and parsing the same resume file a second time when the user starts searching.
      form.append("profile_json", JSON.stringify(previewProfile))
      options = {
        resumeLabel: file?.name || "履歷檔案",
        initialStatus: "準備搜尋…",
      }
    } else if (file) {
      form.append("file", file)
    } else if (text.trim()) {
      form.append("resume_text", text)
    } else if (activeProfile) {
      form.append("profile_json", JSON.stringify(activeProfile.profile))
      options = {
        resumeLabel: activeProfile.resumeLabel || activeProfile.label || "目前 Profile",
        updateActiveProfile: false,
        initialStatus: "準備搜尋…",
      }
    } else {
      setError("請先上傳履歷檔案，或貼上履歷文字。")
      return
    }
    appendSearchOptions(form)
    go(form, options)
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return
    resetResumeRecognition()
    setFile(f)
    setResumeTextOpen(false)
    setError("")
    e.target.value = ""
  }

  const pick = async (m: JobMatch) => onPick(await resolveJd(m.job), profile, m)

  const roleSuggestions = profileTargetRoles(previewProfile || activeProfile?.profile)
  const scopeDescription = useMemo(() => describeSearchScope({
    regions,
    workModes,
    includeInferredWorkMode,
    maxExperienceYears,
    salaryUnit,
    minSalary,
    maxSalary,
    includeUnknownSalary,
    companies,
    pages,
  }), [
    regions,
    workModes,
    includeInferredWorkMode,
    maxExperienceYears,
    salaryUnit,
    minSalary,
    maxSalary,
    includeUnknownSalary,
    companies,
    pages,
  ])
  const displayedCounties = useMemo(() => {
    if (allRegionsOpen) return COUNTIES
    return [...new Set([...COUNTIES.slice(0, 6), ...regions])]
  }, [allRegionsOpen, regions])
  const allMatches = useMemo(() => [...jobs, ...companyJobs], [jobs, companyJobs])
  const visibleJobs = useMemo(
    () => filterJobMatches(jobs, resultRefinement),
    [jobs, resultRefinement],
  )
  const visibleCompany = useMemo(
    () => filterJobMatches(companyJobs, resultRefinement),
    [companyJobs, resultRefinement],
  )
  const visibleCount = visibleJobs.length + visibleCompany.length
  const hasResults = jobs.length > 0 || companyJobs.length > 0

  return (
    <div>
      {(formOpen || !hasResults) && (
      <Card className="p-5 mb-5">
        <div className="mb-4 flex items-start gap-2.5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">
            <Search className="h-4 w-4" />
          </span>
          <div>
            <h2 className="font-semibold text-slate-900">找適合你的職缺</h2>
            <p className="text-xs text-slate-500">
              選好履歷、確認目標職稱就能開始；其他條件都可以略過。
            </p>
          </div>
        </div>
        {!publicWeb && (
          <div
            className="mb-4 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1"
            role="radiogroup"
            aria-label="職缺搜尋模式"
          >
          <button
            type="button"
            role="radio"
            aria-checked={searchMode === "local"}
            disabled={busy}
            onClick={() => setSearchMode("local")}
            className={`rounded-lg px-2.5 py-2 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
              searchMode === "local"
                ? "bg-white text-emerald-800 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <span className="flex items-center justify-center gap-1.5 text-sm font-semibold">
              <ShieldCheck className="h-4 w-4" />
              免 AI
              <span className="hidden text-[10px] font-normal text-emerald-600 sm:inline">0 token</span>
            </span>
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={searchMode === "ai"}
            disabled={busy}
            onClick={() => setSearchMode("ai")}
            className={`rounded-lg px-2.5 py-2 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
              searchMode === "ai"
                ? "bg-white text-brand-700 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <span className="flex items-center justify-center gap-1.5 text-sm font-semibold">
              <Sparkles className="h-4 w-4" />
              AI 精準
            </span>
          </button>
          </div>
        )}

        <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
              <FileText className="h-4 w-4 text-slate-500" />
              履歷
            </span>
            {file ? (
              <span className="inline-flex min-w-0 items-center gap-1.5 rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                <Upload className="h-3.5 w-3.5 shrink-0" />
                <span className="max-w-44 truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={removeResumeFile}
                  aria-label="移除已選檔案"
                  className="rounded p-0.5 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ) : text.trim() ? (
              <span className="rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                已貼上履歷文字
              </span>
            ) : activeProfile ? (
              <span className="inline-flex min-w-0 items-center gap-1.5 rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                <UserRound className="h-3.5 w-3.5 shrink-0" />
                <span className="max-w-44 truncate">{profileDisplayName(activeProfile.profile)}</span>
              </span>
            ) : (
              <span className="text-xs text-slate-400">尚未選擇</span>
            )}
          </div>
          <div className="mt-2.5 flex flex-wrap gap-2">
            <label className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 focus-within:ring-2 focus-within:ring-brand-300 ${busy ? "pointer-events-none opacity-50" : ""}`}>
              <Upload className="h-3.5 w-3.5" />
              {file ? "更換檔案" : "上傳 PDF / DOCX"}
              <input type="file" accept=".pdf,.docx,.txt" className="sr-only" onChange={onFile} disabled={busy} />
            </label>
            <button
              type="button"
              onClick={() => setResumeTextOpen((open) => !open)}
              disabled={busy || !!file}
              aria-expanded={resumeTextOpen}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50"
            >
              {resumeTextOpen ? "收起文字" : text.trim() ? "編輯文字" : "改用貼上文字"}
            </button>
            <button
              type="button"
              onClick={loadSampleResume}
              disabled={busy}
              className="px-1.5 py-1.5 text-xs text-slate-500 hover:text-brand-600 disabled:opacity-50"
            >
              載入合成範例
            </button>
          </div>
          {resumeTextOpen && !file && (
            <textarea
              className="mt-2.5 h-28 w-full rounded-lg border border-slate-300 bg-white p-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
              placeholder="貼上履歷文字…"
              value={text}
              onChange={(event) => changeResumeText(event.target.value)}
            />
          )}
          {activeProfile && !file && !text.trim() && (
            <p className="mt-2 truncate text-xs text-slate-500">
              將使用目前 Profile：{profileSummary(activeProfile.profile)}
            </p>
          )}
          {publicWeb && (
            <p className="mt-2 text-[11px] leading-4 text-slate-500">
              支援 PDF、DOCX、TXT（上限 5 MB）。伺服器只在這次請求解析內容，
              不建立履歷紀錄；離開後若要重新搜尋，需再次選擇檔案。
            </p>
          )}
        </div>

        <TargetRoleEditor
          roles={targetRoles}
          suggestions={roleSuggestions}
          onChange={changeTargetRoles}
          disabled={busy}
          loading={previewBusy}
          previewError={previewError}
        />

        <button
          type="button"
          onClick={() => setScopeOpen((open) => !open)}
          disabled={busy}
          aria-expanded={scopeOpen}
          aria-controls={scopePanelId}
          className="mt-4 flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-left transition hover:border-slate-300 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50"
        >
          <Settings2 className="h-4 w-4 shrink-0 text-slate-500" />
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium text-slate-800">搜尋條件</span>
            <span className="block truncate text-xs text-slate-500">
              {scopeDescription.items.join(" · ")}
            </span>
          </span>
          {scopeDescription.activeCount > 0 && (
            <Badge tone="brand">已設定 {scopeDescription.activeCount}</Badge>
          )}
          {scopeOpen
            ? <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" />
            : <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />}
        </button>

        <div
          id={scopePanelId}
          className={`${scopeOpen ? "flex" : "hidden"} mt-3 flex-col rounded-xl border border-slate-200 p-3`}
        >

        <details className="order-3 mt-4 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
          <summary className="cursor-pointer text-sm font-medium text-slate-700">
            更多條件：薪資、年資、指定公司與搜尋深度
          </summary>
          <div className="pt-1">
        <div className="mt-4">
          <label className="text-sm font-medium text-slate-700 mb-1.5 flex items-center gap-1.5">
            <Building2 className="w-4 h-4 text-slate-400" />也想盯哪些公司？（選填）
          </label>
          <div className="flex flex-wrap items-center gap-1.5 border border-slate-300 rounded-lg px-2 py-1.5 focus-within:ring-2 focus-within:ring-brand-200">
            {companies.map((c) => (
              <span key={c} className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 rounded-md pl-2 pr-1 py-0.5 text-sm">
                {c}
                <button type="button" onClick={() => removeCompany(c)} aria-label={`移除 ${c}`}
                  className="rounded hover:bg-brand-100 p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            <input
              value={companyInput}
              onChange={(e) => setCompanyInput(e.target.value)}
              onKeyDown={onCompanyKey}
              onBlur={() => addCompany(companyInput)}
              disabled={busy}
              aria-label="新增公司名稱"
              placeholder={companies.length ? "再加一間…" : "請填寫公司名並按下 Enter"}
              className="flex-1 min-w-[10rem] bg-transparent text-sm py-0.5 focus:outline-none disabled:opacity-50"
            />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {searchMode === "local"
              ? "免 AI 模式只查 104 / LinkedIn / Cake 等求職網站；結果會列在「指定公司的職缺」獨立區塊。"
              : "這些公司在 104 / LinkedIn / Cake 與官網 careers 的開缺，會列在下方「指定公司的職缺」獨立區塊。"}
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <label htmlFor="pages-select" className="flex shrink-0 items-center gap-1.5 font-medium text-slate-700">
            <Layers className="w-4 h-4 text-slate-400" />每個來源抓幾頁
          </label>
          <select
            id="pages-select"
            value={pages}
            onChange={(e) => setPages(Number(e.target.value))}
            disabled={busy}
            className="shrink-0 border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
          >
            {Array.from({ length: Math.max(1, maxSearchPages) }, (_, index) => index + 1).map((n) => (
              <option key={n} value={n}>{n} 頁</option>
            ))}
          </select>
          <span className="basis-full text-xs text-slate-400 sm:basis-auto">
            頁數越多找得越全，但搜尋與{searchMode === "local" ? "比對" : "評分"}也越久（預設 2 頁）。
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <label htmlFor="experience-select" className="font-medium text-slate-700 flex items-center gap-1.5">
            <Timer className="w-4 h-4 text-slate-400" />最高可接受要求年資
          </label>
          <select
            id="experience-select"
            value={maxExperienceYears}
            onChange={(e) => setMaxExperienceYears(e.target.value)}
            disabled={busy}
            className="border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
          >
            {EXPERIENCE_FILTER_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>{o.label}</option>
            ))}
          </select>
          <span className="text-xs text-slate-400">只排除明確高於門檻的職缺；未標示年資者會保留。</span>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <label htmlFor="salary-unit-select" className="font-medium text-slate-700 flex items-center gap-1.5">
            <Coins className="w-4 h-4 text-slate-400" />薪資篩選
          </label>
          <select
            id="salary-unit-select"
            value={salaryUnit}
            onChange={(e) => setSalaryUnit(e.target.value as SalaryUnit)}
            disabled={busy}
            className="border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
          >
            <option value="monthly">月薪</option>
            <option value="annual">年薪</option>
          </select>
          <input
            type="number"
            min="0"
            step="1000"
            inputMode="numeric"
            value={minSalary}
            onChange={(e) => setMinSalary(e.target.value)}
            disabled={busy}
            placeholder={salaryUnit === "annual" ? "最低年薪" : "最低月薪"}
            className="w-28 border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
          />
          <span className="text-slate-400">–</span>
          <input
            type="number"
            min="0"
            step="1000"
            inputMode="numeric"
            value={maxSalary}
            onChange={(e) => setMaxSalary(e.target.value)}
            disabled={busy}
            placeholder={salaryUnit === "annual" ? "最高年薪" : "最高月薪"}
            className="w-28 border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
          />
          <label className="inline-flex items-center gap-1.5 text-xs text-slate-500">
            <input
              type="checkbox"
              checked={includeUnknownSalary}
              onChange={(e) => setIncludeUnknownSalary(e.target.checked)}
              disabled={busy}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-300 disabled:opacity-50"
            />
            保留面議 / 未標示
          </label>
        </div>
          </div>
        </details>

        <div className="order-1">
          <label className="text-sm font-medium text-slate-700 mb-1.5 flex items-center gap-1.5">
            <Laptop className="w-4 h-4 text-slate-400" />工作型態（選填、可多選）
          </label>
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => setWorkModes([])}
              disabled={busy}
              aria-pressed={workModes.length === 0}
              className={`px-2.5 py-1 rounded-lg border text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
                workModes.length === 0
                  ? "bg-brand-600 text-white border-brand-600"
                  : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              不限工作型態
            </button>
            {WORK_MODE_OPTIONS.map((option) => {
              const on = workModes.includes(option.value)
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => toggleWorkMode(option.value)}
                  disabled={busy}
                  aria-pressed={on}
                  className={`px-2.5 py-1 rounded-lg border text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
                    on
                      ? "bg-brand-600 text-white border-brand-600"
                      : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {option.label}
                </button>
              )
            })}
            <label className={`ml-1 inline-flex items-center gap-1.5 text-xs ${
              workModes.length ? "text-slate-600" : "text-slate-400"
            }`}>
              <input
                type="checkbox"
                checked={includeInferredWorkMode}
                onChange={(e) => setIncludeInferredWorkMode(e.target.checked)}
                disabled={busy || workModes.length === 0}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-300 disabled:opacity-50"
              />
              包含 JD 文字推測
            </label>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            預設只顯示網站明確標示的結果；勾選文字推測會找到更多職缺，但可能需要向公司再次確認。
            結果卡會標明判斷依據。
          </p>
        </div>

        <div className="order-2 mt-4">
          <label className="text-sm font-medium text-slate-700 mb-1.5 flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-slate-400" />搜尋地點（選填、可多選；不選＝全台）
          </label>
          <div className="flex flex-wrap gap-1.5">
            <button type="button" onClick={() => setRegions([])} disabled={busy} aria-pressed={regions.length === 0}
              className={`px-2.5 py-1 rounded-lg border text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
                regions.length === 0 ? "bg-brand-600 text-white border-brand-600" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}>不限縣市</button>
            {displayedCounties.map((c) => {
              const on = regions.includes(c)
              return (
                <button key={c} type="button" onClick={() => toggleRegion(c)} disabled={busy} aria-pressed={on}
                  className={`px-2.5 py-1 rounded-lg border text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
                    on ? "bg-brand-600 text-white border-brand-600" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}>{c}</button>
              )
            })}
            <button
              type="button"
              onClick={() => setAllRegionsOpen((open) => !open)}
              disabled={busy}
              className="px-2.5 py-1 text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
            >
              {allRegionsOpen ? "收起其他縣市" : `其他 ${COUNTIES.length - 6} 個縣市`}
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-1">選了縣市就只找那些地區的職缺，所有來源一致生效（104 直接從來源端篩，其餘來源依職缺地點過濾）。</p>
        </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={onStart} loading={busy} icon={Search}>
            {hasResults
              ? `重新搜尋並${searchMode === "local" ? "比對" : "評分"}`
              : searchMode === "local" ? "免 AI 開始找職缺" : "使用 AI 找職缺"}
          </Button>
          {busy && <Button variant="danger" onClick={stopSearch} icon={XCircle}>停止</Button>}
          {busy && status && (
            <span className="text-sm text-slate-500 inline-flex items-center gap-1">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />{status}
            </span>
          )}
        </div>
        {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
        {queries.length > 0 && (
          <div className="mt-3 text-sm text-slate-600 flex flex-wrap items-center gap-1.5">
            <span className="text-slate-500">搜尋關鍵字：</span>
            {queries.map((q, i) => <Badge key={i} tone="slate">{q}</Badge>)}
          </div>
        )}
        {sources.length > 0 && (
          <div className="mt-2 text-xs text-slate-500 flex flex-wrap gap-3">
            {sources.map((s, i) => (
              <span key={i} className={`inline-flex items-center gap-1 ${s.blocked ? "text-slate-400" : "text-emerald-600"}`}>
                {s.blocked ? <XCircle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                {SRC_LABEL[s.source] || s.source}{s.blocked ? " 暫無" : ` ${s.count}`}
              </span>
            ))}
          </div>
        )}
      </Card>
      )}

      {blockedNote && (
        <div className="mb-3 text-sm bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />{blockedNote}
        </div>
      )}

      <DiscoveryInsights profile={profile} skillGap={skillGap} mode={resultMode} />

      {resultMode === "ai"
        && profile
        && (profile as Record<string, unknown>).parse_degraded === true && (
        <div className="mb-3 text-sm bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>
            AI 後端呼叫失敗，目前是<b>本機備援解析</b>（定位、技能與搜尋關鍵字可能不準）。
            請確認右上角的 AI 引擎（Claude Code / Codex）已安裝並登入，再重新搜尋以取得精準結果。
          </span>
        </div>
      )}

      {/* 結果標題 + 進度 */}
      {(jobs.length > 0 || (busy && rankTotal > 0)) && (
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <h2 className="font-semibold flex items-center gap-2">
            {resultMode === "local" ? "免 AI 履歷配對職缺" : "AI 推薦職缺"}（依適配度排序）
            {fallback && <Badge tone="amber">範例資料</Badge>}
          </h2>
          {busy && rankTotal > 0 && (
            <span className="text-sm text-slate-500 inline-flex items-center gap-1">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              已{resultMode === "local" ? "比對" : "評分"} {jobs.length} / {rankTotal}
            </span>
          )}
          {busy && <Button size="sm" variant="danger" onClick={stopSearch} icon={XCircle}>停止</Button>}
        </div>
      )}

      {hasResults && (
        <ResultRefinementBar
          matches={allMatches}
          value={resultRefinement}
          visibleCount={visibleCount}
          onChange={setResultRefinement}
        />
      )}

      {busy && jobs.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Card key={i} className="p-4 flex gap-4">
              <Skeleton className="w-14 h-14 rounded-xl" />
              <div className="flex-1 space-y-2 py-1">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-3 w-1/3" />
                <Skeleton className="h-3 w-3/4" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {done && jobs.length === 0 && !error && (
        <Card className="p-2">
          <EmptyState
            icon={Search}
            title="這次沒有取得職缺結果"
            desc={workModes.length
              ? "目前工作型態條件沒有符合結果；可增加搜尋頁數、改選其他型態，或開啟 JD 文字推測後再試。"
              : "即時來源可能暫時被擋，可調整履歷內容、搜尋頁數或條件後再試。"}
            action={linkedin ? (
              <a href={linkedin} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
                <ExternalLink className="w-4 h-4" />直接到 LinkedIn 搜尋
              </a>
            ) : undefined}
          />
        </Card>
      )}

      {visibleJobs.length > 0 && (
        <JobList
          matches={visibleJobs}
          onPick={pick}
          allowPackageGeneration={!publicWeb}
        />
      )}
      {jobs.length > 0 && visibleJobs.length === 0 && (
        <p className="text-sm text-slate-400">目前結果篩選沒有符合的職缺，放寬條件看看。</p>
      )}

      {/* 指定公司的職缺（獨立區塊、獨立排序） */}
      {(companyJobs.length > 0 || (done && searchedCompanies.length > 0)) && (
        <div className="mt-8">
          <h2 className="font-semibold flex items-center gap-2 mb-3">
            <Building2 className="w-4 h-4 text-brand-600" />指定公司的職缺（依適配度排序）
            {searchedCompanies.length > 0 && <span className="text-sm font-normal text-slate-400">{searchedCompanies.join("、")}</span>}
          </h2>
          {visibleCompany.length > 0 ? (
            <JobList
              matches={visibleCompany}
              onPick={pick}
              allowPackageGeneration={!publicWeb}
            />
          ) : companyJobs.length > 0 ? (
            <p className="text-sm text-slate-400">目前結果篩選沒有符合的公司職缺。</p>
          ) : (
            <Card className="p-2">
              <EmptyState icon={Building2} title="指定公司目前查無相關開缺"
                desc={resultMode === "local"
                  ? "可能沒有在 104 / LinkedIn / Cake 等來源刊登；可直接到公司官網看看。"
                  : "可能沒有在 104 / LinkedIn / Cake PO，或官網 careers 抓不到；可直接到公司官網看看。"} />
            </Card>
          )}
        </div>
      )}

    </div>
  )
}
