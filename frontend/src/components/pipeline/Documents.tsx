import type { ComponentType, ReactNode } from "react"
import type {
  MatchReport, CompanyBrief, TailoredResume, CoverLetter, InterviewKit, CritiqueReport,
} from "../../types"
import { ScoreRing } from "../ScoreRing"
import { Card } from "../../ui/Card"
import { Badge } from "../../ui/Badge"
import {
  Target, Building2, FileText, Mail, MessageSquare, ShieldCheck,
  CheckCircle2, AlertTriangle,
} from "../../ui/icons"

type Tone = "brand" | "emerald" | "amber" | "rose" | "slate"

const EDIT_CLS =
  "w-full border border-brand-200 bg-brand-50/30 rounded-lg p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"

function Tags({ items, tone }: { items: string[]; tone: Tone }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((t, i) => <Badge key={i} tone={tone}>{t}</Badge>)}
    </div>
  )
}

function Section(
  { icon: Icon, title, children }:
  { icon: ComponentType<{ className?: string }>; title: string; children: ReactNode },
) {
  return (
    <Card className="p-5 avoid-break animate-fade-in-up">
      <h3 className="font-bold mb-3 flex items-center gap-2 text-slate-900">
        <span className="grid place-items-center w-7 h-7 rounded-lg bg-brand-50 text-brand-600">
          <Icon className="w-4 h-4" />
        </span>
        {title}
      </h3>
      {children}
    </Card>
  )
}

function Label({ children }: { children: ReactNode }) {
  return <p className="text-sm font-medium mt-3 mb-1.5 text-slate-700">{children}</p>
}

export function MatchCard({ m }: { m: MatchReport }) {
  return (
    <Section icon={Target} title="匹配評分">
      <div className="flex items-center gap-5 mb-2">
        <ScoreRing score={m.score} size={96} />
        <div>
          <p className="text-sm font-medium flex items-center gap-1.5">
            {m.recommend_proceed
              ? <><CheckCircle2 className="w-4 h-4 text-emerald-600" />建議續做</>
              : <><AlertTriangle className="w-4 h-4 text-amber-500" />建議再評估</>}
          </p>
          <p className="text-sm text-slate-600 mt-1">{m.reason}</p>
        </div>
      </div>
      {m.matched.length > 0 && (<><Label>符合項</Label><Tags items={m.matched} tone="emerald" /></>)}
      {m.gaps.length > 0 && (<><Label>落差項</Label><Tags items={m.gaps} tone="rose" /></>)}
      {m.suggestions.length > 0 && (
        <ul className="list-disc pl-5 text-sm mt-3 space-y-1 text-slate-700">
          {m.suggestions.map((s, i) => <li key={i}>{s}</li>)}
        </ul>
      )}
    </Section>
  )
}

export function CompanyCard({ c }: { c: CompanyBrief }) {
  return (
    <Section icon={Building2} title={`公司情報：${c.company}`}>
      {(c.note || c.data_limited) && (
        <p className="text-xs text-amber-600 mb-2 flex items-center gap-1">
          <AlertTriangle className="w-3.5 h-3.5" />{c.note || "公開資料有限，建議自行補查"}
        </p>
      )}
      <dl className="grid grid-cols-2 gap-2 text-sm">
        {c.industry && <><dt className="text-slate-500">產業</dt><dd>{c.industry}</dd></>}
        {c.size && <><dt className="text-slate-500">規模</dt><dd>{c.size}</dd></>}
        {c.salary_range && <><dt className="text-slate-500">薪資範圍</dt><dd>{c.salary_range}</dd></>}
        {c.funding && <><dt className="text-slate-500">資金</dt><dd>{c.funding}</dd></>}
      </dl>
      {c.culture_summary && <p className="text-sm mt-3 text-slate-700">{c.culture_summary}</p>}
      {c.benefits.length > 0 && (<><Label>福利</Label><Tags items={c.benefits} tone="brand" /></>)}
      {c.red_flags.length > 0 && (<><Label>避雷紅旗</Label><Tags items={c.red_flags} tone="rose" /></>)}
      {c.recent_news.length > 0 && (
        <ul className="list-disc pl-5 text-sm mt-3 space-y-1 text-slate-700">
          {c.recent_news.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}
    </Section>
  )
}

export function ResumeDoc(
  { r, summary, bullets, onSummary, onBullets }:
  {
    r: TailoredResume
    summary?: string
    bullets?: string  // 換行分隔
    onSummary?: (v: string) => void
    onBullets?: (v: string) => void
  },
) {
  const sum = summary ?? r.summary
  const blistText = bullets ?? r.bullets.join("\n")
  const blist = blistText.split("\n").filter((b) => b.trim())
  const editable = Boolean(onSummary || onBullets)  // 工作台給 handler → 可編輯；歷史檢視沒給 → 唯讀
  return (
    <Section icon={FileText} title="客製履歷">
      {/* 螢幕：直接可編輯（不需切換按鈕） */}
      {editable && (
        <div className="no-print space-y-2">
          <textarea className={`${EDIT_CLS} h-16`} value={sum} aria-label="履歷專業摘要"
            onChange={(e) => onSummary?.(e.target.value)} placeholder="專業摘要" />
          <textarea className={`${EDIT_CLS} h-32`} value={blistText} aria-label="履歷重點（一行一個）"
            onChange={(e) => onBullets?.(e.target.value)} placeholder="一行一個重點…" />
        </div>
      )}
      {/* 唯讀排版：列印時用（可編輯時），或歷史檢視時直接顯示 */}
      <div className={editable ? "hidden print:block" : ""}>
        <p className="text-sm font-medium mb-2 text-slate-800">{sum}</p>
        <ul className="list-disc pl-5 text-sm space-y-1 text-slate-700">
          {blist.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
      </div>
      {r.ats_keywords_hit.length > 0 && (<><Label>ATS 命中</Label><Tags items={r.ats_keywords_hit} tone="emerald" /></>)}
      {r.ats_keywords_missing.length > 0 && (<><Label>ATS 尚缺</Label><Tags items={r.ats_keywords_missing} tone="amber" /></>)}
      {r.notes && <p className="text-xs text-slate-500 mt-3">{r.notes}</p>}
    </Section>
  )
}

export function CoverLetterDoc(
  { c, subject, body, onSubject, onBody }:
  {
    c: CoverLetter
    subject?: string
    body?: string
    onSubject?: (v: string) => void
    onBody?: (v: string) => void
  },
) {
  const subj = subject ?? c.subject ?? ""
  const text = body ?? c.body
  const editable = Boolean(onSubject || onBody)  // 工作台給 handler → 可編輯；歷史檢視沒給 → 唯讀
  return (
    <Section icon={Mail} title="求職信">
      {/* 螢幕：直接可編輯 */}
      {editable && (
        <div className="no-print space-y-2">
          <input className={EDIT_CLS} value={subj} aria-label="求職信主旨"
            onChange={(e) => onSubject?.(e.target.value)} placeholder="主旨" />
          <textarea className={`${EDIT_CLS} h-48`} value={text} aria-label="求職信內文"
            onChange={(e) => onBody?.(e.target.value)} placeholder="求職信內文…" />
        </div>
      )}
      {/* 唯讀排版：列印時用（可編輯時），或歷史檢視時直接顯示 */}
      <div className={editable ? "hidden print:block" : ""}>
        {subj && <p className="text-sm font-medium mb-2 text-slate-800">主旨：{subj}</p>}
        <div className="text-sm whitespace-pre-wrap leading-relaxed text-slate-700">{text}</div>
      </div>
    </Section>
  )
}

function QList({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null
  return (
    <div className="mt-3">
      <Label>{title}</Label>
      <ul className="list-disc pl-5 text-sm space-y-1 text-slate-700">
        {items.map((q, i) => <li key={i}>{q}</li>)}
      </ul>
    </div>
  )
}

export function InterviewKitDoc({ k }: { k: InterviewKit }) {
  return (
    <Section icon={MessageSquare} title="面試準備">
      <QList title="技術題" items={k.technical_questions} />
      <QList title="行為題" items={k.behavioral_questions} />
      <QList title="台灣特有題" items={k.taiwan_specific_questions} />
      <QList title="STAR 擬答" items={k.sample_answers} />
      <QList title="反向提問" items={k.reverse_questions} />
      <QList title="避雷提醒" items={k.cautions} />
    </Section>
  )
}

export function CritiqueCard({ q }: { q: CritiqueReport }) {
  const rows: [string, number][] = [
    ["履歷", q.resume_score], ["求職信", q.cover_letter_score], ["面試", q.interview_score],
  ]
  const tone = (s: number) => (s >= 80 ? "text-emerald-600" : s >= 60 ? "text-amber-500" : "text-rose-600")
  return (
    <Section icon={ShieldCheck} title="品管評審">
      <p className="text-sm mb-3 flex items-center gap-1.5">
        {q.overall_pass
          ? <><CheckCircle2 className="w-4 h-4 text-emerald-600" />整體達標</>
          : <><AlertTriangle className="w-4 h-4 text-amber-500" />未達標（已觸發重寫）</>}
      </p>
      <div className="grid grid-cols-3 gap-3">
        {rows.map(([label, score]) => (
          <div key={label} className="text-center rounded-lg bg-slate-50 py-3">
            <div className={`text-2xl font-bold ${tone(score)}`}>{score}</div>
            <div className="text-xs text-slate-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>
      {q.feedback.length > 0 && (
        <ul className="list-disc pl-5 text-sm mt-3 space-y-1 text-slate-700">
          {q.feedback.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      )}
    </Section>
  )
}
