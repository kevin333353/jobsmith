import { useState } from "react"
import type { ChangeEvent } from "react"
import type { JobMatch } from "../types"
import { readSSE } from "../sse"
import { SAMPLE_RESUME } from "../sampleResume"

const SRC_LABEL: Record<string, string> = { "104": "104", yourator: "Yourator", cake: "Cake" }

function fitColor(s: number) {
  return s >= 80 ? "bg-emerald-600" : s >= 60 ? "bg-amber-500" : "bg-slate-400"
}

export function JobSearchView({ onPick }: { onPick: (jd: string) => void }) {
  const [text, setText] = useState("")
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState("")
  const [queries, setQueries] = useState<string[]>([])
  const [sources, setSources] = useState<{ source: string; count: number; blocked: boolean }[]>([])
  const [jobs, setJobs] = useState<JobMatch[]>([])
  const [linkedin, setLinkedin] = useState("")
  const [error, setError] = useState("")

  async function go(form: FormData) {
    setBusy(true); setError(""); setJobs([]); setQueries([]); setSources([]); setLinkedin("")
    setStatus("上傳中…")
    try {
      const resp = await fetch("/api/jobs/auto", { method: "POST", body: form })
      await readSSE(resp, (ev) => {
        if (ev.type === "progress") setStatus(ev.message)
        else if (ev.type === "queries") setQueries(ev.queries)
        else if (ev.type === "source")
          setSources((s) => [...s, { source: ev.source, count: ev.count, blocked: ev.blocked }])
        else if (ev.type === "jobs") setJobs(ev.data as JobMatch[])
        else if (ev.type === "linkedin") setLinkedin(ev.url)
        else if (ev.type === "error") setError(ev.message)
        else if (ev.type === "done") setStatus("完成 ✅")
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
    onPick(jd)
  }

  return (
    <div>
      <div className="bg-white border rounded-xl p-5 mb-5">
        <p className="text-sm text-slate-600 mb-2">丟上你的履歷，AI 自動推導關鍵字、搜尋 104 / Yourator / Cake，並依你的履歷排序適合的職缺。</p>
        <textarea
          className="w-full border rounded-lg p-3 text-sm h-32"
          placeholder="貼上履歷文字…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="flex flex-wrap gap-2 mt-3 items-center">
          <button onClick={onSubmitText} disabled={busy}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
            開始自動找職缺
          </button>
          <button onClick={() => setText(SAMPLE_RESUME)} disabled={busy}
            className="px-4 py-2 bg-slate-200 rounded-lg text-sm">載入範例履歷</button>
          <label className="px-4 py-2 bg-slate-200 rounded-lg text-sm cursor-pointer">
            上傳檔案（PDF/DOCX/TXT）
            <input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={onFile} disabled={busy} />
          </label>
          {status && <span className="text-sm text-slate-500">⏳ {status}</span>}
        </div>
        {error && <p className="text-sm text-rose-600 mt-2">{error}</p>}
        {queries.length > 0 && (
          <div className="mt-3 text-sm text-slate-600">
            搜尋關鍵字：{queries.map((q, i) => (
              <span key={i} className="inline-block bg-slate-100 rounded-full px-2 py-0.5 mr-1">{q}</span>
            ))}
          </div>
        )}
        {sources.length > 0 && (
          <div className="mt-2 text-xs text-slate-500 flex flex-wrap gap-2">
            {sources.map((s, i) => (
              <span key={i}>{SRC_LABEL[s.source] || s.source}：{s.blocked ? "✗ 略過" : `✓ ${s.count}`}</span>
            ))}
          </div>
        )}
      </div>

      {jobs.length > 0 && (
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">推薦職缺（依適配度排序）</h2>
          {linkedin && (
            <a href={linkedin} target="_blank" rel="noreferrer"
              className="text-sm text-indigo-600 underline">也到 LinkedIn 搜尋 ↗</a>
          )}
        </div>
      )}

      <div className="space-y-3">
        {jobs.map((m, i) => (
          <div key={i} className="bg-white border rounded-xl p-4 flex gap-4">
            <div className={`shrink-0 w-12 h-12 rounded-lg text-white flex items-center justify-center font-bold ${fitColor(m.fit_score)}`}>
              {m.fit_score}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <a href={m.job.url} target="_blank" rel="noreferrer"
                  className="font-medium text-slate-900 hover:underline">{m.job.title}</a>
                <span className="text-xs bg-slate-100 text-slate-500 rounded-full px-2 py-0.5">
                  {SRC_LABEL[m.job.source] || m.job.source}
                </span>
              </div>
              <p className="text-sm text-slate-600">
                {m.job.company}
                {m.job.location ? `｜${m.job.location}` : ""}
                {m.job.salary ? `｜${m.job.salary}` : ""}
              </p>
              {m.reason && <p className="text-sm text-slate-700 mt-1">{m.reason}</p>}
              {m.matched.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {m.matched.map((t, k) => (
                    <span key={k} className="text-xs bg-emerald-100 text-emerald-700 rounded-full px-2 py-0.5">{t}</span>
                  ))}
                </div>
              )}
            </div>
            <div className="shrink-0 flex flex-col gap-2">
              <button onClick={() => pick(m)}
                className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm whitespace-nowrap">產生投遞包</button>
              <a href={m.job.url} target="_blank" rel="noreferrer"
                className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-sm text-center whitespace-nowrap">看原職缺</a>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
