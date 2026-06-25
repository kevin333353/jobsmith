import { useState } from "react"
import type { JobMatch } from "../../types"
import { SRC_LABEL } from "../../lib/sources"
import { Card } from "../../ui/Card"
import { Button } from "../../ui/Button"
import { Badge } from "../../ui/Badge"
import { Sparkles, ExternalLink, ChevronLeft, ChevronRight } from "../../ui/icons"

const PAGE_SIZE = 8

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

function JobCard({ m, onPick, pending }: { m: JobMatch; onPick: (m: JobMatch) => void; pending?: boolean }) {
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
        <Button size="sm" icon={Sparkles} loading={pending} onClick={() => onPick(m)} className="whitespace-nowrap">產生投遞包</Button>
        <a href={m.job.url} target="_blank" rel="noreferrer"
          className="inline-flex items-center justify-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-sm hover:bg-slate-200 transition whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
          <ExternalLink className="w-3.5 h-3.5" />看原職缺
        </a>
      </div>
    </Card>
  )
}

// 可分頁的職缺清單；onPick 可為 async（抓完整 JD 時該卡按鈕顯示載入中）。
export function JobList({ matches, onPick }:
  { matches: JobMatch[]; onPick: (m: JobMatch) => void | Promise<void> }) {
  const [page, setPage] = useState(1)
  const [pendingUrl, setPendingUrl] = useState("")
  // 新一輪結果（matches 參考改變）→ 在 render 期回到第 1 頁（React 官方「prop 改變時
  // 調整 state」做法：用 state 記錄上一批比對，免 effect、不讀寫 ref）。
  const [prevMatches, setPrevMatches] = useState(matches)
  if (prevMatches !== matches) {
    setPrevMatches(matches)
    setPage(1)
  }
  const totalPages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE))
  const cur = Math.min(page, totalPages)

  async function handle(m: JobMatch) {
    if (pendingUrl) return  // 已有一張卡在抓 JD/開跑 → 忽略連點，避免同時觸發多條 pipeline
    setPendingUrl(m.job.url)
    try { await onPick(m) } finally { setPendingUrl("") }
  }

  return (
    <>
      <div className="space-y-3">
        {matches.slice((cur - 1) * PAGE_SIZE, cur * PAGE_SIZE).map((m, i) => (
          <JobCard key={i} m={m} onPick={handle} pending={!!pendingUrl && m.job.url === pendingUrl} />
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
