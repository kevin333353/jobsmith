import { useState } from "react"
import type { UserProfile, InterviewQuestion, AnswerFeedback, InterviewSummary } from "../types"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Badge } from "../ui/Badge"
import { EmptyState } from "../ui/EmptyState"
import { ScoreRing } from "../components/ScoreRing"
import { MessagesSquare, CheckCircle2, AlertTriangle, RefreshCw, ArrowRight } from "../ui/icons"

export function InterviewView({ fallbackProfile }: { fallbackProfile?: UserProfile | null }) {
  const [jd, setJd] = useState("")
  const [phase, setPhase] = useState<"idle" | "running" | "done">("idle")
  const [questions, setQuestions] = useState<InterviewQuestion[]>([])
  const [idx, setIdx] = useState(0)
  const [answer, setAnswer] = useState("")
  const [feedback, setFeedback] = useState<AnswerFeedback | null>(null)
  const [transcript, setTranscript] = useState<{ question: string; answer: string; score: number }[]>([])
  const [summary, setSummary] = useState<InterviewSummary | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function loadSample() {
    const j = await (await fetch("/api/sample")).json()
    setJd(j.jd_text)
  }

  async function start() {
    if (!jd.trim()) { setError("請先貼上或載入職缺 JD"); return }
    setBusy(true); setError(""); setSummary(null); setFeedback(null); setTranscript([]); setIdx(0)
    try {
      const r = await fetch("/api/interview/start", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jd, profile: fallbackProfile ?? null }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.error || "啟動失敗"); return }
      setQuestions(d.questions || [])
      setPhase("running")
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。")
    } finally {
      setBusy(false)
    }
  }

  async function submitAnswer() {
    if (!answer.trim() || busy) return
    setBusy(true); setError("")
    try {
      const q = questions[idx]
      const r = await fetch("/api/interview/answer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jd, question: q.question, answer, profile: fallbackProfile ?? null }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.error || "評分失敗"); return }
      setFeedback(d as AnswerFeedback)
      setTranscript((t) => [...t, { question: q.question, answer, score: (d as AnswerFeedback).score }])
    } catch {
      setError("連線發生問題。")
    } finally {
      setBusy(false)
    }
  }

  async function next() {
    if (idx < questions.length - 1) {
      setIdx((i) => i + 1); setAnswer(""); setFeedback(null)
      return
    }
    // 最後一題 → 總評
    setBusy(true); setError("")
    try {
      const r = await fetch("/api/interview/summary", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jd, transcript: transcript.map((t) => ({ question: t.question, answer: t.answer })) }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.error || "總評失敗"); return }
      setSummary(d as InterviewSummary); setPhase("done")
    } catch {
      setError("連線發生問題。")
    } finally {
      setBusy(false)
    }
  }

  function restart() {
    setPhase("idle"); setQuestions([]); setIdx(0); setAnswer("")
    setFeedback(null); setTranscript([]); setSummary(null); setError("")
  }

  // ---- idle：輸入 JD ----
  if (phase === "idle") {
    return (
      <div>
        <Card className="p-5 mb-5">
          <p className="text-sm text-slate-600 mb-2">貼上目標職缺 JD，AI 面試官會依你的履歷出題、逐題給回饋與評分。</p>
          <textarea
            className="w-full border border-slate-300 rounded-lg p-3 text-sm h-32 focus:outline-none focus:ring-2 focus:ring-brand-200"
            placeholder="貼上職缺 JD 文字…" value={jd} onChange={(e) => setJd(e.target.value)}
          />
          <div className="flex flex-wrap gap-2 mt-3">
            <Button onClick={start} loading={busy} icon={MessagesSquare}>開始面試</Button>
            <Button variant="secondary" onClick={loadSample} disabled={busy}>載入範例 JD</Button>
          </div>
          {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
        </Card>
        {!fallbackProfile && (
          <Card className="p-2">
            <EmptyState icon={MessagesSquare} title="先到「自動找職缺」或「履歷健檢」提供履歷"
              desc="面試官會依你的真實背景出題；沒有履歷時會用範例背景示意。" />
          </Card>
        )}
      </div>
    )
  }

  // ---- done：總評 ----
  if (phase === "done" && summary) {
    return (
      <div className="space-y-4 animate-fade-in-up">
        <Card className="p-6 flex items-center gap-6">
          <ScoreRing score={summary.overall_score} size={110} />
          <div>
            <h2 className="text-lg font-bold mb-1">面試總評</h2>
            <p className="text-sm text-slate-600">{summary.summary}</p>
          </div>
        </Card>
        {summary.advice.length > 0 && (
          <Card className="p-5">
            <h3 className="font-bold mb-2 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-500" />接下來最該補強</h3>
            <ul className="list-disc pl-5 text-sm space-y-1 text-slate-700">
              {summary.advice.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          </Card>
        )}
        <Button variant="secondary" icon={RefreshCw} onClick={restart}>再來一場</Button>
      </div>
    )
  }

  // ---- running：逐題 ----
  const q = questions[idx]
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">第 {idx + 1} / {questions.length} 題</span>
        <Button variant="ghost" size="sm" icon={RefreshCw} onClick={restart}>重新開始</Button>
      </div>
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-2">
          {q?.category && <Badge tone="brand">{q.category}</Badge>}
          <span className="text-xs text-slate-400">面試官提問</span>
        </div>
        <p className="text-base font-medium text-slate-900">{q?.question}</p>
      </Card>

      {!feedback ? (
        <Card className="p-5">
          <textarea
            className="w-full border border-slate-300 rounded-lg p-3 text-sm h-36 focus:outline-none focus:ring-2 focus:ring-brand-200"
            placeholder="輸入你的回答…" value={answer} onChange={(e) => setAnswer(e.target.value)}
          />
          <div className="mt-3">
            <Button onClick={submitAnswer} loading={busy} disabled={!answer.trim()} icon={CheckCircle2}>送出回答</Button>
          </div>
        </Card>
      ) : (
        <Card className="p-5 avoid-break animate-fade-in-up">
          <div className="flex items-center gap-4 mb-3">
            <ScoreRing score={feedback.score} size={84} />
            <div className="text-sm text-slate-600">這題的即時回饋</div>
          </div>
          {feedback.strengths.length > 0 && (<>
            <p className="text-sm font-medium mt-2 mb-1 text-emerald-700 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" />做得好</p>
            <ul className="list-disc pl-5 text-sm space-y-1 text-slate-700">{feedback.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </>)}
          {feedback.improvements.length > 0 && (<>
            <p className="text-sm font-medium mt-3 mb-1 text-amber-700 flex items-center gap-1"><AlertTriangle className="w-4 h-4" />可改進</p>
            <ul className="list-disc pl-5 text-sm space-y-1 text-slate-700">{feedback.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </>)}
          {feedback.sample_answer && (<>
            <p className="text-sm font-medium mt-3 mb-1 text-slate-700">示範答法</p>
            <p className="text-sm whitespace-pre-wrap leading-relaxed text-slate-600 bg-slate-50 rounded-lg p-3">{feedback.sample_answer}</p>
          </>)}
          <div className="mt-4">
            <Button onClick={next} loading={busy} icon={ArrowRight}>
              {idx < questions.length - 1 ? "下一題" : "看總評"}
            </Button>
          </div>
        </Card>
      )}
      {error && <p className="text-sm text-rose-600">{error}</p>}
    </div>
  )
}
