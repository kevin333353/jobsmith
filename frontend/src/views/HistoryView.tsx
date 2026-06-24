import { useEffect, useState } from "react"
import type { MouseEvent } from "react"
import type { UserProfile } from "../types"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Badge } from "../ui/Badge"
import { EmptyState } from "../ui/EmptyState"
import {
  MatchCard, CompanyCard, ResumeDoc, CoverLetterDoc, InterviewKitDoc, CritiqueCard,
} from "../components/pipeline/Documents"
import { Archive, Trash2, ArrowLeft, FileDown, Printer, Workflow } from "../ui/icons"

interface PkgSummary {
  id: number; created_at: string; job_title: string; company: string; match_score: number; approved: number
}

function fmtDate(iso: string) {
  try { return new Date(iso).toLocaleString("zh-TW", { dateStyle: "medium", timeStyle: "short" }) }
  catch { return iso }
}

export function HistoryView(
  { active, onReopen }:
  { active: boolean; onReopen: (jd: string, profile?: UserProfile | null) => void },
) {
  const [list, setList] = useState<PkgSummary[]>([])
  const [detail, setDetail] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    try {
      const d = await (await fetch("/api/history")).json()
      setList(d.packages || [])
    } catch { /* 靜默 */ }
  }
  useEffect(() => { if (active) refresh() }, [active])

  async function open(id: number) {
    setBusy(true)
    try { setDetail(await (await fetch(`/api/history/${id}`)).json()) }
    finally { setBusy(false) }
  }

  async function del(id: number, e: MouseEvent) {
    e.stopPropagation()
    await fetch(`/api/history/${id}`, { method: "DELETE" })
    if (detail?.id === id) setDetail(null)
    refresh()
  }

  async function downloadDocx(pkg: any) {
    const r = pkg.tailored_resume, c = pkg.cover_letter, k = pkg.interview_kit
    const body = {
      job_title: pkg.parsed_job?.title || "求職投遞包",
      company: pkg.parsed_job?.company || pkg.company_brief?.company || "",
      resume: r ? { summary: r.summary, bullets: r.bullets, ats_keywords_hit: r.ats_keywords_hit } : undefined,
      cover_letter: c ? { subject: c.subject, body: c.body } : undefined,
      interview: k || undefined,
    }
    const resp = await fetch("/api/export/docx", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    })
    if (!resp.ok) return
    const blob = await resp.blob()
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob); a.download = "投遞包.docx"; a.click(); URL.revokeObjectURL(a.href)
  }

  // ---- 詳情檢視 ----
  if (detail) {
    const p = detail.package || {}
    return (
      <div>
        <button onClick={() => setDetail(null)}
          className="no-print text-sm text-brand-600 hover:text-brand-700 mb-3 inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" />回列表
        </button>
        <div className="no-print flex flex-wrap gap-2 mb-4">
          <Button variant="secondary" icon={Workflow}
            onClick={() => onReopen(detail.jd_text || "", detail.profile ?? null)}>重新開啟到工作台</Button>
          <Button variant="secondary" icon={FileDown} onClick={() => downloadDocx(p)}>下載 Word</Button>
          <Button variant="secondary" icon={Printer} onClick={() => window.print()}>列印 / 匯出 PDF</Button>
        </div>
        <div className="space-y-4">
          {p.match_report && <MatchCard m={p.match_report} />}
          {p.company_brief && <CompanyCard c={p.company_brief} />}
          {p.tailored_resume && <ResumeDoc r={p.tailored_resume} />}
          {p.cover_letter && <CoverLetterDoc c={p.cover_letter} />}
          {p.interview_kit && <InterviewKitDoc k={p.interview_kit} />}
          {p.critique && <CritiqueCard q={p.critique} />}
        </div>
      </div>
    )
  }

  // ---- 清單 ----
  if (!list.length) {
    return (
      <Card className="p-2">
        <EmptyState icon={Archive} title="還沒有投遞包紀錄"
          desc="到「投遞包工作台」跑完一份投遞包後，會自動存到這裡，可回查、重新開啟、下載。" />
      </Card>
    )
  }
  return (
    <div className="space-y-3">
      <h2 className="font-semibold">我的投遞包（{list.length}）</h2>
      {list.map((p) => (
        <Card key={p.id} interactive className="p-4 flex items-center gap-4 cursor-pointer"
          onClick={() => open(p.id)}>
          <div className={`shrink-0 w-12 h-12 rounded-xl grid place-items-center font-bold text-white ${
            p.match_score >= 80 ? "bg-emerald-600" : p.match_score >= 60 ? "bg-amber-500" : "bg-slate-400"}`}>
            {p.match_score}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-900 truncate">{p.job_title}</p>
            <p className="text-sm text-slate-600 truncate">
              {p.company}{p.approved ? "" : ""} · {fmtDate(p.created_at)}
              {p.approved ? <Badge tone="emerald" className="ml-2">已核可</Badge> : null}
            </p>
          </div>
          <button onClick={(e) => del(p.id, e)} aria-label={`刪除 ${p.job_title}`} title="刪除"
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") e.stopPropagation() }}
            className="shrink-0 p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300">
            <Trash2 className="w-4 h-4" />
          </button>
        </Card>
      ))}
      {busy && <p className="text-sm text-slate-400">載入中…</p>}
    </div>
  )
}
