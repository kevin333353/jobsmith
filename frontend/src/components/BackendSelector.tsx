import { useEffect, useState } from "react"
import { Cpu } from "../ui/icons"

interface BackendOption { id: string; label: string; available: boolean }

// 讓使用者切換 LLM 後端（Claude Code CLI / Codex CLI 訂閱，仿 open-design）。
export function BackendSelector() {
  const [options, setOptions] = useState<BackendOption[]>([])
  const [current, setCurrent] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    fetch("/api/backend")
      .then((r) => r.json())
      .then((d) => { setOptions(d.options || []); setCurrent(d.current || "") })
      .catch(() => {})
  }, [])

  async function change(id: string) {
    setBusy(true)
    const prev = current
    setCurrent(id)
    try {
      const r = await fetch("/api/backend", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ backend: id }),
      })
      if (!r.ok) setCurrent(prev)
    } catch {
      setCurrent(prev)
    } finally {
      setBusy(false)
    }
  }

  if (!options.length) return null
  return (
    <label className="no-print flex items-center gap-2 text-xs text-slate-500">
      <Cpu className="w-4 h-4 text-slate-400" />
      <span className="hidden sm:inline">引擎</span>
      <select
        value={current}
        disabled={busy}
        onChange={(e) => change(e.target.value)}
        className="border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs bg-white text-slate-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brand-200"
      >
        {options.map((o) => (
          <option key={o.id} value={o.id} disabled={!o.available}>
            {o.label}{o.available ? "" : "（未偵測到）"}
          </option>
        ))}
      </select>
    </label>
  )
}
