import { useEffect, useState } from "react"
import type { ChangeEvent, KeyboardEvent as ReactKeyboardEvent } from "react"
import type { JobMatch, UserProfile, SkillGapReport } from "../types"
import { readSSE } from "../sse"
import { SAMPLE_RESUME } from "../sampleResume"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Badge } from "../ui/Badge"
import { Skeleton } from "../ui/Skeleton"
import { EmptyState } from "../ui/EmptyState"
import { Search, Upload, Loader2, ExternalLink, Sparkles, AlertTriangle, CheckCircle2, XCircle, ChevronLeft, ChevronRight, Target, Building2, X } from "../ui/icons"

const PAGE_SIZE = 8

const SRC_LABEL: Record<string, string> = {
  "104": "104", yourator: "Yourator", linkedin: "LinkedIn", cake: "Cake", careers: "官網", sample: "範例",
}

function fitGradient(s: number) {
  return s >= 80 ? "from-emerald-500 to-emerald-600"
    : s >= 60 ? "from-amber-500 to-amber-600"
      : "from-slate-400 to-slate-500"
}

function FitBadge({ score }: { score: number }) {
  return (
    <div className={`shrink-0 w-14 h-14 rounded-xl bg-gradient-to-br ${fitGradient(score)} text-white grid place-items-center text-center`}>
      <div className="text-lg font-bold leading-none">{score}</div>
      <div className="text-[9px] opacity-85 mt-0.5">適配</div>
    </div>
  )
}

// 一筆職缺卡（AI 推薦與指定公司共用）。
function JobCard({ m, onPick }: { m: JobMatch; onPick: (m: JobMatch) => void }) {
  return (
    <Card interactive className="p-4 flex flex-col sm:flex-row gap-4 animate-fade-in-up">
      <FitBadge score={m.fit_score} />
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <a href={m.job.url} target="_blank" rel="noreferrer"
            className="font-medium text-slate-900 hover:text-brand-700 hover:underline rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">{m.job.title}</a>
          <Badge tone={m.job.source === "careers" ? "brand" : "slate"}>{SRC_LABEL[m.job.source] || m.job.source}</Badge>
        </div>
        <p className="text-sm text-slate-600 mt-0.5">
          {m.job.company}
          {m.job.location ? `｜${m.job.location}` : ""}
          {m.job.salary ? `｜${m.job.salary}` : ""}
        </p>
        {m.reason && <p className="text-sm text-slate-700 mt-1">{m.reason}</p>}
        {m.matched.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {m.matched.map((t, k) => <Badge key={k} tone="emerald">{t}</Badge>)}
          </div>
        )}
      </div>
      <div className="shrink-0 flex flex-row sm:flex-col gap-2">
        <Button size="sm" icon={Sparkles} onClick={() => onPick(m)} className="whitespace-nowrap">產生投遞包</Button>
        <a href={m.job.url} target="_blank" rel="noreferrer"
          className="inline-flex items-center justify-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-sm hover:bg-slate-200 transition whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
          <ExternalLink className="w-3.5 h-3.5" />看原職缺
        </a>
      </div>
    </Card>
  )
}

// 一段可分頁的職缺清單（AI 推薦、指定公司各用一個，分頁互不影響）。
function JobList({ matches, onPick }: { matches: JobMatch[]; onPick: (m: JobMatch) => void }) {
  const [page, setPage] = useState(1)
  useEffect(() => { setPage(1) }, [matches])  // 新一輪結果回到第 1 頁
  const totalPages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE))
  const cur = Math.min(page, totalPages)
  return (
    <>
      <div className="space-y-3">
        {matches.slice((cur - 1) * PAGE_SIZE, cur * PAGE_SIZE).map((m, i) => (
          <JobCard key={i} m={m} onPick={onPick} />
        ))}
      </div>
      {matches.length > PAGE_SIZE && (
        <nav aria-label="職缺分頁" className="flex items-center justify-center gap-1.5 mt-5">
          <Button variant="secondary" size="sm" icon={ChevronLeft}
            disabled={cur <= 1} onClick={() => setPage(Math.max(1, cur - 1))}>上一頁</Button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
            <button key={n} onClick={() => setPage(n)} aria-current={n === cur ? "page" : undefined}
              className={`w-8 h-8 rounded-lg text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                n === cur ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}>{n}</button>
          ))}
          <Button variant="secondary" size="sm" onClick={() => setPage(Math.min(totalPages, cur + 1))}
            disabled={cur >= totalPages}>下一頁<ChevronRight className="w-4 h-4" /></Button>
        </nav>
      )}
    </>
  )
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
  const [sources, setSources] = useState<{ source: string; count: number; blocked: boolean }[]>([])
  const [jobs, setJobs] = useState<JobMatch[]>([])
  const [companyJobs, setCompanyJobs] = useState<JobMatch[]>([])
  const [linkedin, setLinkedin] = useState("")
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [blockedNote, setBlockedNote] = useState("")
  const [fallback, setFallback] = useState(false)
  const [error, setError] = useState("")
  const [skillGap, setSkillGap] = useState<SkillGapReport | null>(null)
  // 公司名單（選填）：除了 AI 自動找，使用者可加入想盯的公司，獨立區塊顯示。
  const [companies, setCompanies] = useState<string[]>([])
  const [companyInput, setCompanyInput] = useState("")
  // 上傳的履歷檔：先存著，等使用者按「開始」才送（不再上傳即自動找）。
  const [file, setFile] = useState<File | null>(null)
  // 這次送出時實際查詢的公司（用於「查無結果」提示，與輸入框內容脫鉤）。
  const [searchedCompanies, setSearchedCompanies] = useState<string[]>([])

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

  async function go(form: FormData) {
    // 把尚未變成標籤的輸入也一併送出（並回填成標籤，讓 UI 一致）。
    const trailing = companyInput.trim()
    const cs = trailing ? (companies.includes(trailing) ? companies : [...companies, trailing]) : companies
    if (trailing) { setCompanies(cs); setCompanyInput("") }
    if (cs.length) form.append("companies", cs.join(","))
    setSearchedCompanies(cs)

    setBusy(true); setDone(false); setError(""); setJobs([]); setCompanyJobs([]); setQueries([]); setSources([])
    setLinkedin(""); setProfile(null); setBlockedNote(""); setFallback(false); setSkillGap(null)
    setStatus("上傳中…")
    try {
      const resp = await fetch("/api/jobs/auto", { method: "POST", body: form })
      await readSSE(resp, (ev) => {
        if (ev.type === "progress") setStatus(ev.message)
        else if (ev.type === "profile") { setProfile(ev.data as UserProfile); onProfile?.(ev.data as UserProfile) }
        else if (ev.type === "queries") setQueries(ev.queries)
        else if (ev.type === "source")
          // 後端會搜尋前 2 個關鍵字、再加每間指定公司，同一來源會回報多次 → 依來源彙整。
          setSources((s) => {
            const idx = s.findIndex((x) => x.source === ev.source)
            if (idx < 0) return [...s, { source: ev.source, count: ev.count, blocked: ev.blocked }]
            const copy = [...s]
            copy[idx] = {
              source: ev.source,
              count: copy[idx].count + ev.count,
              blocked: copy[idx].blocked && ev.blocked,
            }
            return copy
          })
        else if (ev.type === "all_blocked") setBlockedNote(ev.message)
        else if (ev.type === "jobs") { setJobs(ev.data as JobMatch[]); setFallback(Boolean(ev.fallback)) }
        else if (ev.type === "company_jobs") setCompanyJobs(ev.data as JobMatch[])
        else if (ev.type === "skill_gap") setSkillGap(ev.data as SkillGapReport)
        else if (ev.type === "linkedin") setLinkedin(ev.url)
        else if (ev.type === "error") setError(ev.message)
        else if (ev.type === "done") setDone(true)
      })
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。")
    } finally {
      setBusy(false); setStatus("")
    }
  }

  // 按「開始自動找職缺」：有上傳檔就送檔，否則送貼上的文字。上傳檔本身不會自動開跑。
  function onStart() {
    const form = new FormData()
    if (file) {
      form.append("file", file)
    } else if (text.trim()) {
      form.append("resume_text", text)
    } else {
      setError("請先貼上履歷文字，或上傳履歷檔案"); return
    }
    go(form)
  }
  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return
    setFile(f); setError(""); e.target.value = ""
  }

  function pick(m: JobMatch) {
    const j = m.job
    const jd = [
      j.title,
      `公司：${j.company}`,
      j.location ? `地點：${j.location}` : "",
      j.salary ? `薪資：${j.salary}` : "",
      "",
      j.snippet || "",
      j.requirements.length ? `\n需求：${j.requirements.join("、")}` : "",
    ].filter(Boolean).join("\n")
    onPick(jd, profile)
  }

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

      {skillGap && skillGap.top_demand.length > 0 && (() => {
        const max = skillGap.top_demand[0].count || 1
        return (
          <Card className="p-5 mb-4">
            <h3 className="font-bold mb-3 flex items-center gap-2 text-slate-900">
              <span className="grid place-items-center w-7 h-7 rounded-lg bg-brand-50 text-brand-600"><Target className="w-4 h-4" /></span>
              技能缺口分析
            </h3>
            {skillGap.your_gaps.length > 0 && (
              <>
                <p className="text-sm font-medium mb-1.5 text-slate-700">你最該補的技能（市場在要、你還沒有）</p>
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {skillGap.your_gaps.slice(0, 12).map((g, i) => (
                    <Badge key={i} tone="rose">{g.skill} ×{g.count}</Badge>
                  ))}
                </div>
              </>
            )}
            <p className="text-sm font-medium mb-1.5 text-slate-700">市場熱門技能</p>
            <div className="space-y-1.5">
              {skillGap.top_demand.slice(0, 8).map((d, i) => {
                const has = skillGap.have.some((h) => h.toLowerCase() === d.skill.toLowerCase())
                return (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="w-28 shrink-0 truncate text-slate-600">{d.skill}</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${has ? "bg-emerald-500" : "bg-brand-500"}`}
                        style={{ width: `${(d.count / max) * 100}%` }} />
                    </div>
                    <span className="w-6 text-right text-slate-400 text-xs">{d.count}</span>
                  </div>
                )
              })}
            </div>
          </Card>
        )
      })()}

      {/* ① AI 依履歷推薦 */}
      {jobs.length > 0 && (
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold flex items-center gap-2">
            AI 推薦職缺（依適配度排序）
            {fallback && <Badge tone="amber">範例資料</Badge>}
          </h2>
          {linkedin && (
            <a href={linkedin} target="_blank" rel="noreferrer"
              className="text-sm text-brand-600 hover:underline inline-flex items-center gap-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
              也到 LinkedIn 搜尋 <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
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

      {jobs.length > 0 && <JobList matches={jobs} onPick={pick} />}

      {/* ② 指定公司的職缺（獨立區塊、獨立排序） */}
      {(companyJobs.length > 0 || (done && searchedCompanies.length > 0)) && (
        <div className="mt-8">
          <h2 className="font-semibold flex items-center gap-2 mb-3">
            <Building2 className="w-4 h-4 text-brand-600" />指定公司的職缺（依適配度排序）
            {searchedCompanies.length > 0 && <span className="text-sm font-normal text-slate-400">{searchedCompanies.join("、")}</span>}
          </h2>
          {companyJobs.length > 0 ? (
            <JobList matches={companyJobs} onPick={pick} />
          ) : (
            <Card className="p-2">
              <EmptyState icon={Building2} title="指定公司目前查無相關開缺"
                desc="可能沒有在 104 / LinkedIn / Cake PO，或官網 careers 抓不到；可直接到公司官網看看。" />
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
