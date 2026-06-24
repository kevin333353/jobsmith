import { useState } from "react"
import type { ChangeEvent } from "react"
import type { ResumeAssessment, UserProfile } from "../types"
import { readSSE } from "../sse"
import { SAMPLE_RESUME } from "../sampleResume"
import { Dashboard } from "../components/Dashboard"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Skeleton } from "../ui/Skeleton"
import { EmptyState } from "../ui/EmptyState"
import { Gauge, Upload, Loader2 } from "../ui/icons"

export function ResumeHealthView({ onProfile }: { onProfile?: (p: UserProfile) => void }) {
  const [text, setText] = useState("")
  const [status, setStatus] = useState("")
  const [busy, setBusy] = useState(false)
  const [assessment, setAssessment] = useState<ResumeAssessment | null>(null)
  const [error, setError] = useState("")

  async function evaluate(form: FormData) {
    setBusy(true); setError(""); setAssessment(null); setStatus("上傳中…")
    try {
      const resp = await fetch("/api/resume/evaluate", { method: "POST", body: form })
      await readSSE(resp, (ev) => {
        if (ev.type === "progress") setStatus(ev.message)
        else if (ev.type === "profile") onProfile?.(ev.data as UserProfile)  // 共用真實履歷給投遞包工作台
        else if (ev.type === "assessment") setAssessment(ev.data as ResumeAssessment)
        else if (ev.type === "error") setError(ev.message)
        else if (ev.type === "done") setStatus("完成 ✅")
      })
    } catch {
      setError("連線發生問題，請確認伺服器是否啟動。")
    } finally {
      setBusy(false)
    }
  }

  function onSubmitText() {
    if (!text.trim()) { setError("請先貼上或載入履歷文字"); return }
    const form = new FormData()
    form.append("resume_text", text)
    evaluate(form)
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    const form = new FormData()
    form.append("file", f)
    evaluate(form)
    e.target.value = ""
  }

  return (
    <div>
      <Card className="p-5 mb-6">
        <textarea
          className="w-full border border-slate-300 rounded-lg p-3 text-sm h-40 focus:outline-none focus:ring-2 focus:ring-brand-200"
          placeholder="貼上履歷文字…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="flex flex-wrap gap-2 mt-3 items-center">
          <Button onClick={onSubmitText} loading={busy} icon={Gauge}>開始健檢</Button>
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
      </Card>

      {busy && !assessment && (
        <div className="space-y-6">
          <Card className="p-6 flex items-center gap-6">
            <Skeleton className="w-28 h-28 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </Card>
        </div>
      )}

      {!busy && !assessment && !error && (
        <Card className="p-2">
          <EmptyState
            icon={Gauge}
            title="貼上或上傳你的履歷，開始健檢"
            desc="AI 會評分表達清晰度、量化成果、ATS 關鍵字與台灣慣例，並給出可改進項目與改寫範例。"
          />
        </Card>
      )}

      {assessment && <Dashboard a={assessment} />}
    </div>
  )
}
