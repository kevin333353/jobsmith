import { useState } from "react"
import type { ChangeEvent } from "react"
import type { JobMatch, UserProfile } from "../types"
import { readSSE } from "../sse"
import { SAMPLE_RESUME } from "../sampleResume"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Badge } from "../ui/Badge"
import { Skeleton } from "../ui/Skeleton"
import { EmptyState } from "../ui/EmptyState"
import { Search, Upload, Loader2, ExternalLink, Sparkles, AlertTriangle, CheckCircle2, XCircle } from "../ui/icons"

const SRC_LABEL: Record<string, string> = {
  "104": "104", yourator: "Yourator", cake: "Cake", sample: "範例",
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
  const [linkedin, setLinkedin] = useState("")
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [blockedNote, setBlockedNote] = useState("")
  const [fallback, setFallback] = useState(false)
  const [error, setError] = useState("")

  async function go(form: FormData) {
    setBusy(true); setDone(false); setError(""); setJobs([]); setQueries([]); setSources([])
    setLinkedin(""); setProfile(null); setBlockedNote(""); setFallback(false)
    setStatus("上傳中…")
    try {
      const resp = await fetch("/api/jobs/auto", { method: "POST", body: form })
      await readSSE(resp, (ev) => {
        if (ev.type === "progress") setStatus(ev.message)
        else if (ev.type === "profile") { setProfile(ev.data as UserProfile); onProfile?.(ev.data as UserProfile) }
        else if (ev.type === "queries") setQueries(ev.queries)
        else if (ev.type === "source")
          // 後端會搜尋前 2 個關鍵字，同一來源會回報多次 → 依來源彙整（筆數加總；全部被擋才算略過）
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

  function onSubmitText() {
    if (!text.trim()) { setError("請先貼上或載入履歷文字"); return }
    const form = new FormData(); form.append("resume_text", text); go(form)
  }
  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return
    const form = new FormData(); form.append("file", f); go(form); e.target.value = ""
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
          丟上你的履歷，AI 自動推導關鍵字、搜尋 104 / Yourator / Cake，並依你的履歷排序適合的職缺。
        </p>
        <textarea
          className="w-full border border-slate-300 rounded-lg p-3 text-sm h-32 focus:outline-none focus:ring-2 focus:ring-brand-200"
          placeholder="貼上履歷文字…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="flex flex-wrap gap-2 mt-3 items-center">
          <Button onClick={onSubmitText} loading={busy} icon={Search}>開始自動找職缺</Button>
          <Button variant="secondary" onClick={() => setText(SAMPLE_RESUME)} disabled={busy}>載入範例履歷</Button>
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
                {SRC_LABEL[s.source] || s.source}{s.blocked ? " 略過" : ` ${s.count}`}
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

      {jobs.length > 0 && (
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold flex items-center gap-2">
            推薦職缺（依適配度排序）
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

      <div className="space-y-3">
        {jobs.map((m, i) => (
          <Card key={i} interactive className="p-4 flex flex-col sm:flex-row gap-4 animate-fade-in-up">
            <FitBadge score={m.fit_score} />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <a href={m.job.url} target="_blank" rel="noreferrer"
                  className="font-medium text-slate-900 hover:text-brand-700 hover:underline rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">{m.job.title}</a>
                <Badge tone="slate">{SRC_LABEL[m.job.source] || m.job.source}</Badge>
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
              <Button size="sm" icon={Sparkles} onClick={() => pick(m)} className="whitespace-nowrap">產生投遞包</Button>
              <a href={m.job.url} target="_blank" rel="noreferrer"
                className="inline-flex items-center justify-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-sm hover:bg-slate-200 transition whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
                <ExternalLink className="w-3.5 h-3.5" />看原職缺
              </a>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
