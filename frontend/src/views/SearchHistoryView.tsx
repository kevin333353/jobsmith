import { useEffect, useState } from "react"
import type { MouseEvent } from "react"
import type { UserProfile, JobMatch } from "../types"
import { resolveJd } from "../lib/resolveJd"
import { JobList } from "../components/jobs/JobList"
import { Card } from "../ui/Card"
import { Badge } from "../ui/Badge"
import { EmptyState } from "../ui/EmptyState"
import { Search, Trash2, ArrowLeft, Building2, Target } from "../ui/icons"

interface SearchSummary {
  id: number; created_at: string; label: string; ai_count: number; company_count: number
}

function fmtDate(iso: string) {
  try { return new Date(iso).toLocaleString("zh-TW", { dateStyle: "medium", timeStyle: "short" }) }
  catch { return iso }
}

export function SearchHistoryView(
  { active, onPick }:
  { active: boolean; onPick: (jd: string, profile?: UserProfile | null) => void },
) {
  const [list, setList] = useState<SearchSummary[]>([])
  const [detail, setDetail] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try { setList((await (await fetch("/api/searches")).json()).searches || []) }
    catch { /* 靜默 */ }
  }
  useEffect(() => { if (active) refresh() }, [active])

  async function open(id: number) {
    setBusy(true)
    try { setDetail(await (await fetch(`/api/searches/${id}`)).json()) }
    finally { setBusy(false) }
  }

  async function del(id: number, e: MouseEvent) {
    e.stopPropagation()
    await fetch(`/api/searches/${id}`, { method: "DELETE" })
    if (detail?.id === id) setDetail(null)
    refresh()
  }

  // ---- 詳情：顯示當時的 AI 推薦 + 指定公司 + 技能缺口 ----
  if (detail) {
    const p = detail.payload || {}
    const profile: UserProfile | null = detail.profile || null
    const aiJobs: JobMatch[] = p.jobs || []
    const companyJobs: JobMatch[] = p.companyJobs || []
    const gap = p.skillGap
    const pick = async (m: JobMatch) => onPick(await resolveJd(m.job), profile)
    return (
      <div>
        <button onClick={() => setDetail(null)}
          className="text-sm text-brand-600 hover:text-brand-700 mb-3 inline-flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 rounded">
          <ArrowLeft className="w-4 h-4" />回搜尋紀錄
        </button>
        <h2 className="font-semibold mb-1">{detail.label}</h2>
        <p className="text-sm text-slate-500 mb-4">{fmtDate(detail.created_at)}</p>

        {gap && gap.your_gaps?.length > 0 && (
          <Card className="p-4 mb-4">
            <h3 className="font-bold mb-2 flex items-center gap-2 text-slate-900">
              <Target className="w-4 h-4 text-brand-600" />當時的技能缺口
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {gap.your_gaps.slice(0, 12).map((g: { skill: string; count: number }, i: number) => (
                <Badge key={i} tone="rose">{g.skill} ×{g.count}</Badge>
              ))}
            </div>
          </Card>
        )}

        {aiJobs.length > 0 && (
          <>
            <h3 className="font-semibold mb-3">AI 推薦職缺（{aiJobs.length}）</h3>
            <JobList matches={aiJobs} onPick={pick} />
          </>
        )}
        {companyJobs.length > 0 && (
          <div className="mt-8">
            <h3 className="font-semibold flex items-center gap-2 mb-3">
              <Building2 className="w-4 h-4 text-brand-600" />指定公司的職缺（{companyJobs.length}）
            </h3>
            <JobList matches={companyJobs} onPick={pick} />
          </div>
        )}
        {busy && <p className="text-sm text-slate-400 mt-3">載入中…</p>}
      </div>
    )
  }

  // ---- 清單 ----
  if (!list.length) {
    return (
      <Card className="p-2">
        <EmptyState icon={Search} title="還沒有搜尋紀錄"
          desc="到「自動找職缺」跑一次搜尋，結果會自動存到這裡，可回看、重新產生投遞包、刪除。" />
      </Card>
    )
  }
  return (
    <div className="space-y-3">
      <h2 className="font-semibold">搜尋紀錄（{list.length}）</h2>
      {list.map((s) => (
        <Card key={s.id} interactive className="p-4 flex items-center gap-4 cursor-pointer" onClick={() => open(s.id)}>
          <div className="shrink-0 w-12 h-12 rounded-xl grid place-items-center bg-brand-50 text-brand-600">
            <Search className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-900 truncate">{s.label}</p>
            <p className="text-sm text-slate-600 truncate">
              AI {s.ai_count} 筆{s.company_count ? `・指定公司 ${s.company_count} 筆` : ""} · {fmtDate(s.created_at)}
            </p>
          </div>
          <button onClick={(e) => del(s.id, e)} aria-label={`刪除 ${s.label}`} title="刪除"
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") e.stopPropagation() }}
            className="shrink-0 p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300">
            <Trash2 className="w-4 h-4" />
          </button>
        </Card>
      ))}
    </div>
  )
}
