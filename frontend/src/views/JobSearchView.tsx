import { useEffect, useRef, useState } from "react"
import type { ChangeEvent, KeyboardEvent as ReactKeyboardEvent } from "react"
import type { JobMatch, UserProfile, JobsAutoEvent } from "../types"
import { readSSE } from "../sse"
import { SAMPLE_RESUME } from "../sampleResume"
import { resolveJd } from "../lib/resolveJd"
import { JobList } from "../components/jobs/JobList"
import { SRC_LABEL } from "../lib/sources"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Badge } from "../ui/Badge"
import { Skeleton } from "../ui/Skeleton"
import { EmptyState } from "../ui/EmptyState"
import { Search, Upload, Loader2, ExternalLink, AlertTriangle, CheckCircle2, XCircle, Building2, Layers, MapPin, X } from "../ui/icons"

const SNAP_KEY = "copilot.jobsearch.v1"  // 上次搜尋結果快取（重新整理/重開沿用）

type SourceStat = { source: string; count: number; blocked: boolean }
// 串流累積容器（完成後整包存進搜尋紀錄）；state 更新非同步，存檔讀這裡的即時值。
type SearchAcc = {
  jobs: JobMatch[]; companyJobs: JobMatch[]
  queries: string[]; sources: SourceStat[]; linkedin: string; fallback: boolean
  profile: UserProfile | null
}
// 同分時以 url 決定先後，讓分批串流到達的順序不影響最終排序（可重現）。
const sortByFit = (arr: JobMatch[]) =>
  [...arr].sort((a, b) => b.fit_score - a.fit_score || (a.job.url < b.job.url ? -1 : a.job.url > b.job.url ? 1 : 0))

// 適配色帶分段篩選（內部仍用 fit_score）：全部 / 高(≥80) / 中以上(≥60)。
const FIT_BANDS = [{ v: 0, l: "全部" }, { v: 80, l: "高" }, { v: 60, l: "中以上" }]

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
  { onPick, onProfile }:
  { onPick: (jd: string, profile?: UserProfile | null) => void; onProfile?: (p: UserProfile) => void },
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
  const [minFit, setMinFit] = useState(0)            // 適配色帶門檻（0/60/80）
  const [regions, setRegions] = useState<string[]>([])  // 搜尋地點（縣市 key；空 = 全台）
  const [linkedin, setLinkedin] = useState("")
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [blockedNote, setBlockedNote] = useState("")
  const [fallback, setFallback] = useState(false)
  const [error, setError] = useState("")
  const [companies, setCompanies] = useState<string[]>([])
  const [companyInput, setCompanyInput] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [searchedCompanies, setSearchedCompanies] = useState<string[]>([])
  const [pages, setPages] = useState(2)  // 每個來源抓幾頁（越多越全、但越慢）

  const abortRef = useRef<AbortController | null>(null)  // 取消上一個未完成的搜尋

  // 還原上次搜尋結果：重新整理 / 重開不必重找（僅開啟時還原一次，是 effect 正當用途）。
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SNAP_KEY)
      if (!raw) return
      const s = JSON.parse(raw)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (typeof s.text === "string") setText(s.text)
      if (Array.isArray(s.companies)) setCompanies(s.companies)
      if (Array.isArray(s.jobs)) setJobs(s.jobs)
      if (Array.isArray(s.companyJobs)) setCompanyJobs(s.companyJobs)
      if (Array.isArray(s.queries)) setQueries(s.queries)
      if (Array.isArray(s.sources)) setSources(s.sources)
      if (typeof s.linkedin === "string") setLinkedin(s.linkedin)
      if (typeof s.fallback === "boolean") setFallback(s.fallback)
      if (Array.isArray(s.searchedCompanies)) setSearchedCompanies(s.searchedCompanies)
      if (typeof s.pages === "number") setPages(s.pages)
      if (Array.isArray(s.regions)) setRegions(s.regions)
      if (s.profile) { setProfile(s.profile as UserProfile); onProfile?.(s.profile as UserProfile) }
      if (Array.isArray(s.jobs) && s.jobs.length) setDone(true)
    } catch { /* 忽略毀損快取 */ }
    // 僅開啟時還原一次；onProfile 為穩定的 setState，不需列入依賴。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!done) return
    try {
      localStorage.setItem(SNAP_KEY, JSON.stringify({
        text, companies, jobs, companyJobs, queries, sources,
        linkedin, fallback, searchedCompanies, profile, pages, regions,
      }))
    } catch { /* localStorage 不可用/已滿則略過 */ }
  }, [done, jobs, companyJobs, queries, sources, linkedin, fallback,
      searchedCompanies, profile, text, companies, pages, regions])

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

  async function saveSearch(acc: SearchAcc, cs: string[]) {
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
          },
        }),
      })
    } catch { /* 存檔失敗不影響使用 */ }
  }

  async function go(form: FormData) {
    const trailing = companyInput.trim()
    const cs = trailing ? (companies.includes(trailing) ? companies : [...companies, trailing]) : companies
    if (trailing) { setCompanies(cs); setCompanyInput("") }
    if (cs.length) form.append("companies", cs.join(","))
    setSearchedCompanies(cs)

    abortRef.current?.abort()  // 取消上一個還沒跑完的搜尋，避免兩條串流交錯進同一個 acc
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setBusy(true); setDone(false); setError(""); setJobs([]); setCompanyJobs([]); setQueries([]); setSources([])
    setLinkedin(""); setProfile(null); setBlockedNote(""); setFallback(false); setRankTotal(0)
    setStatus("上傳中…")
    // 串流累積（供完成後存檔；state 更新非同步，存檔讀這裡的即時值）。
    const acc: SearchAcc = { jobs: [], companyJobs: [], queries: [], sources: [], linkedin: "", fallback: false, profile: null }
    try {
      const resp = await fetch("/api/jobs/auto", { method: "POST", body: form, signal: ctrl.signal })
      await readSSE(resp, (ev: JobsAutoEvent) => {
        if (ev.type === "progress") setStatus(ev.message)
        else if (ev.type === "profile") { acc.profile = ev.data; setProfile(ev.data as UserProfile); onProfile?.(ev.data as UserProfile) }
        else if (ev.type === "queries") { acc.queries = ev.queries; setQueries(ev.queries) }
        else if (ev.type === "source") { acc.sources = mergeSource(acc.sources, ev); setSources((s) => mergeSource(s, ev)) }
        else if (ev.type === "all_blocked") setBlockedNote(ev.message)
        else if (ev.type === "rank_start") { acc.fallback = Boolean(ev.fallback); setFallback(Boolean(ev.fallback)); setRankTotal(ev.total || 0); acc.jobs = []; setJobs([]) }
        else if (ev.type === "ranked_batch") {
          acc.jobs = sortByFit([...acc.jobs, ...(ev.data as JobMatch[])])
          setJobs(acc.jobs)
        }
        else if (ev.type === "company_jobs") { acc.companyJobs = sortByFit(ev.data as JobMatch[]); setCompanyJobs(acc.companyJobs) }
        else if (ev.type === "linkedin") { acc.linkedin = ev.url; setLinkedin(ev.url) }
        else if (ev.type === "error") setError(ev.message)
        else if (ev.type === "done") setDone(true)
      })
      await saveSearch(acc, cs)  // 自動存進「搜尋紀錄」
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return  // 被新搜尋取消 → 靜默
      setError("連線發生問題，請確認伺服器是否啟動。")
    } finally {
      if (abortRef.current === ctrl) { setBusy(false); setStatus("") }  // 僅當前搜尋才收尾
    }
  }

  function onStart() {
    const form = new FormData()
    if (file) {
      form.append("file", file)
    } else if (text.trim()) {
      form.append("resume_text", text)
    } else {
      setError("請先貼上履歷文字，或上傳履歷檔案"); return
    }
    form.append("pages", String(pages))
    if (regions.length) form.append("region", regions.join(","))
    go(form)
  }
  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return
    setFile(f); setError(""); e.target.value = ""
  }

  const pick = async (m: JobMatch) => onPick(await resolveJd(m.job), profile)

  const passes = (m: JobMatch) => m.fit_score >= minFit  // 地區已在搜尋時於後端套用
  const visibleJobs = jobs.filter(passes)
  const visibleCompany = companyJobs.filter(passes)
  const hiddenCount = (jobs.length - visibleJobs.length) + (companyJobs.length - visibleCompany.length)

  return (
    <div>
      <Card className="p-5 mb-5">
        <p className="text-sm text-slate-600 mb-2">
          丟上你的履歷，AI 自動推導關鍵字、搜尋 104 / Yourator / LinkedIn / Cake 並依履歷排序；
          也可加入想去的公司，單獨列出它們的開缺。填好後按「開始自動找職缺」。
        </p>
        <textarea
          className="w-full border border-slate-300 rounded-lg p-3 text-sm h-32 focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:bg-slate-50"
          placeholder="貼上履歷文字…（或用下方上傳履歷檔案）"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={!!file}
        />
        {file && (
          <div className="mt-2 inline-flex items-center gap-2 bg-brand-50 text-brand-700 rounded-lg px-3 py-1.5 text-sm">
            <Upload className="w-3.5 h-3.5" />已選擇檔案：{file.name}
            <button type="button" onClick={() => setFile(null)} aria-label="移除已選檔案"
              className="rounded hover:bg-brand-100 p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
              <X className="w-3 h-3" />
            </button>
          </div>
        )}

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
          <p className="text-xs text-slate-400 mt-1">這些公司在 104 / LinkedIn / Cake 與官網 careers 的開缺，會列在下方「指定公司的職缺」獨立區塊。</p>
        </div>

        <div className="mt-4 flex items-center gap-2 text-sm">
          <label htmlFor="pages-select" className="font-medium text-slate-700 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-slate-400" />每個來源抓幾頁
          </label>
          <select
            id="pages-select"
            value={pages}
            onChange={(e) => setPages(Number(e.target.value))}
            disabled={busy}
            className="border border-slate-300 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{n} 頁</option>
            ))}
          </select>
          <span className="text-xs text-slate-400">頁數越多找得越全，但搜尋與評分也越久（預設 2 頁）。</span>
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium text-slate-700 mb-1.5 flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-slate-400" />搜尋地點（選填、可多選；不選＝全台）
          </label>
          <div className="flex flex-wrap gap-1.5">
            <button type="button" onClick={() => setRegions([])} disabled={busy} aria-pressed={regions.length === 0}
              className={`px-2.5 py-1 rounded-lg border text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
                regions.length === 0 ? "bg-brand-600 text-white border-brand-600" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}>不限縣市</button>
            {COUNTIES.map((c) => {
              const on = regions.includes(c)
              return (
                <button key={c} type="button" onClick={() => toggleRegion(c)} disabled={busy} aria-pressed={on}
                  className={`px-2.5 py-1 rounded-lg border text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 ${
                    on ? "bg-brand-600 text-white border-brand-600" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}>{c}</button>
              )
            })}
          </div>
          <p className="text-xs text-slate-400 mt-1">選了縣市就只找那些地區的職缺，所有來源一致生效（104 直接從來源端篩，其餘來源依職缺地點過濾）。</p>
        </div>

        <div className="flex flex-wrap gap-2 mt-4 items-center">
          <Button onClick={onStart} loading={busy} icon={Search}>開始自動找職缺</Button>
          <Button variant="secondary" onClick={() => { setFile(null); setText(SAMPLE_RESUME) }} disabled={busy}>載入範例履歷</Button>
          <label className={`inline-flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 transition cursor-pointer focus-within:ring-2 focus-within:ring-brand-300 ${busy ? "opacity-50 pointer-events-none" : ""}`}>
            <Upload className="w-4 h-4" />上傳檔案（PDF/DOCX/TXT）
            <input type="file" accept=".pdf,.docx,.txt" className="sr-only" onChange={onFile} disabled={busy} />
          </label>
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

      {blockedNote && (
        <div className="mb-3 text-sm bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />{blockedNote}
        </div>
      )}

      {/* 結果標題 + 進度 + 適配色帶篩選 */}
      {(jobs.length > 0 || (busy && rankTotal > 0)) && (
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <h2 className="font-semibold flex items-center gap-2">
            AI 推薦職缺（依適配度排序）
            {fallback && <Badge tone="amber">範例資料</Badge>}
          </h2>
          {busy && rankTotal > 0 && (
            <span className="text-sm text-slate-500 inline-flex items-center gap-1">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />已評分 {jobs.length} / {rankTotal}
            </span>
          )}
          <div className="ml-auto flex items-center gap-1.5 text-sm" role="group" aria-label="適配篩選">
            <span className="text-slate-500">適配</span>
            {FIT_BANDS.map((o) => (
              <button key={o.v} type="button" onClick={() => setMinFit(o.v)} aria-pressed={minFit === o.v}
                className={`px-2.5 py-1 rounded-lg border text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                  minFit === o.v ? "bg-brand-600 text-white border-brand-600" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}>{o.l}</button>
            ))}
          </div>
        </div>
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
            desc="即時來源可能暫時被擋，可調整履歷關鍵字再試。"
            action={linkedin ? (
              <a href={linkedin} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-lg font-medium border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
                <ExternalLink className="w-4 h-4" />直接到 LinkedIn 搜尋
              </a>
            ) : undefined}
          />
        </Card>
      )}

      {visibleJobs.length > 0 && <JobList matches={visibleJobs} onPick={pick} />}
      {jobs.length > 0 && visibleJobs.length === 0 && (
        <p className="text-sm text-slate-400">目前適配篩選沒有符合的職缺，放寬條件看看。</p>
      )}

      {/* 指定公司的職缺（獨立區塊、獨立排序） */}
      {(companyJobs.length > 0 || (done && searchedCompanies.length > 0)) && (
        <div className="mt-8">
          <h2 className="font-semibold flex items-center gap-2 mb-3">
            <Building2 className="w-4 h-4 text-brand-600" />指定公司的職缺（依適配度排序）
            {searchedCompanies.length > 0 && <span className="text-sm font-normal text-slate-400">{searchedCompanies.join("、")}</span>}
          </h2>
          {visibleCompany.length > 0 ? (
            <JobList matches={visibleCompany} onPick={pick} />
          ) : companyJobs.length > 0 ? (
            <p className="text-sm text-slate-400">目前適配篩選沒有符合的公司職缺。</p>
          ) : (
            <Card className="p-2">
              <EmptyState icon={Building2} title="指定公司目前查無相關開缺"
                desc="可能沒有在 104 / LinkedIn / Cake PO，或官網 careers 抓不到；可直接到公司官網看看。" />
            </Card>
          )}
        </div>
      )}

      {hiddenCount > 0 && (
        <p className="text-xs text-slate-400 mt-3">已依篩選條件隱藏 {hiddenCount} 筆職缺。</p>
      )}
    </div>
  )
}
