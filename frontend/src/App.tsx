import { useState } from "react"
import type { ChangeEvent } from "react"
import type { ResumeAssessment } from "./types"
import { readSSE } from "./sse"
import { SAMPLE_RESUME } from "./sampleResume"
import { Dashboard } from "./components/Dashboard"

export default function App() {
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
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <div className="max-w-5xl mx-auto p-6">
        <header className="mb-6">
          <h1 className="text-2xl font-bold">台灣 AI 求職 Co-pilot</h1>
          <p className="text-slate-500">上傳或貼上你的履歷，AI 幫你健檢評分並給出具體改進建議。</p>
        </header>

        <div className="bg-white border rounded-xl p-5 mb-6">
          <textarea
            className="w-full border rounded-lg p-3 text-sm h-40"
            placeholder="貼上履歷文字…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex flex-wrap gap-2 mt-3 items-center">
            <button onClick={onSubmitText} disabled={busy}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
              開始健檢
            </button>
            <button onClick={() => setText(SAMPLE_RESUME)} disabled={busy}
              className="px-4 py-2 bg-slate-200 rounded-lg text-sm">載入範例履歷</button>
            <label className="px-4 py-2 bg-slate-200 rounded-lg text-sm cursor-pointer">
              上傳檔案（PDF/DOCX/TXT）
              <input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={onFile} disabled={busy} />
            </label>
            {status && <span className="text-sm text-slate-500">{status}</span>}
          </div>
          {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
        </div>

        {assessment && <Dashboard a={assessment} />}
      </div>
    </div>
  )
}
