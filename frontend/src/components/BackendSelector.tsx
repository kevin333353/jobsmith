import { useEffect, useState } from "react"
import { Cpu, ChevronDown } from "../ui/icons"

interface BackendOption { id: string; label: string; available: boolean }

// 仿 Open Design：頂部只露本機 CLI（Claude Code / Codex CLI）；anthropic 不在主選單。
const CLI_IDS = ["claude_cli", "codex_cli"]

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
  // 只露兩個本機 CLI；若目前後端是其他（如 anthropic）也保留在清單避免 select 值落空。
  const visible = options.filter((o) => CLI_IDS.includes(o.id) || o.id === current)
  return (
    <label
      title="本機 CLI 訂閱（免 API key）。模型自動分層：解析用 haiku、生成用 sonnet、深思用 opus。"
      className={`no-print inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white pl-3 pr-2 py-1.5 text-xs text-slate-600 shadow-card ${busy ? "opacity-60" : ""}`}
    >
      <Cpu className="w-4 h-4 text-brand-500" />
      <span className="text-slate-400">本機 CLI</span>
      <span className="text-slate-300">·</span>
      <div className="relative inline-flex items-center">
        <select
          value={current}
          disabled={busy}
          aria-label="選擇 LLM 後端"
          onChange={(e) => change(e.target.value)}
          className="appearance-none bg-transparent pr-5 font-medium text-slate-800 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50 cursor-pointer"
        >
          {visible.map((o) => (
            <option key={o.id} value={o.id} disabled={!o.available}>
              {o.label}{o.available ? "" : "（未偵測到）"}
            </option>
          ))}
        </select>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-0 pointer-events-none" />
      </div>
    </label>
  )
}
