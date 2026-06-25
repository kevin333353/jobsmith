import { useEffect, useState } from "react"
import { Brand } from "../ui/Brand"
import { Button } from "../ui/Button"
import { Cpu, CheckCircle2, XCircle, Loader2, ArrowRight, KeyRound } from "../ui/icons"

interface BackendOption { id: string; label: string; available: boolean; kind: string }
interface BackendData {
  options?: BackendOption[]
  current?: string
  byok?: { base_url?: string; model?: string; has_key?: boolean }
}

const ONBOARD_IDS = ["claude_cli", "codex_cli", "openai"]
const CLI_IDS = ["claude_cli", "codex_cli"]

const DESC: Record<string, string> = {
  claude_cli: "使用本機 Claude Code CLI，不需要在本 App 內輸入 API key。",
  codex_cli: "使用本機 Codex CLI，不需要在本 App 內輸入 API key。",
  openai: "使用 OpenAI 相容端點，適合 OpenAI、DeepSeek、Groq、OpenRouter、Ollama、LM Studio。",
}

export function Onboarding({ onDone, onSkip }: { onDone: () => void; onSkip?: () => void }) {
  const [options, setOptions] = useState<BackendOption[]>([])
  const [selected, setSelected] = useState("")
  const [byok, setByok] = useState({ base_url: "", api_key: "", model: "" })
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    fetch("/api/backend")
      .then((r) => r.json())
      .then((d: BackendData) => {
        const opts = (d.options || []).filter((o) => ONBOARD_IDS.includes(o.id))
        setOptions(opts)
        setByok({
          base_url: d.byok?.base_url || "",
          api_key: "",
          model: d.byok?.model || "",
        })
        const firstAvail = opts.find((o) => o.id !== "openai" && o.available)
        setSelected(
          d.current && ONBOARD_IDS.includes(d.current)
            ? d.current
            : (firstAvail?.id || "openai"),
        )
      })
      .catch(() => {
        setOptions([{ id: "openai", label: "OpenAI 相容端點 (BYOK)", available: true, kind: "byok" }])
        setSelected("openai")
      })
  }, [])

  function choose(id: string) {
    setSelected(id)
    setResult(null)
  }

  async function saveByokIfNeeded() {
    if (selected !== "openai") return true
    const r = await fetch("/api/backend/byok", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(byok),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      setResult({ ok: false, message: d.error || "BYOK 設定格式不正確。" })
      return false
    }
    return true
  }

  async function test() {
    if (!selected) return
    setTesting(true)
    setResult(null)
    try {
      if (!(await saveByokIfNeeded())) return
      const r = await fetch("/api/backend/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ backend: selected }),
      })
      const d = await r.json()
      setResult({ ok: Boolean(d.ok), message: d.message || (d.ok ? "測試成功" : "測試失敗") })
    } catch {
      setResult({ ok: false, message: "連線發生問題，請確認伺服器是否啟動。" })
    } finally {
      setTesting(false)
    }
  }

  async function start() {
    if (!selected) return
    setStarting(true)
    try {
      if (!(await saveByokIfNeeded())) return
      await fetch("/api/backend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ backend: selected }),
      })
      onDone()
    } finally {
      setStarting(false)
    }
  }

  const selectedKind = selected === "openai" ? "byok" : "cli"

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm grid place-items-center p-4">
      <div className="w-full max-w-lg bg-white rounded-xl2 shadow-cardHover p-6 animate-fade-in-up">
        <div className="mb-5"><Brand /></div>
        <h1 className="text-lg font-bold text-slate-900 mb-1">選擇 AI 後端</h1>
        <p className="text-sm text-slate-500 mb-4">
          可以使用本機 Claude/Codex CLI，也可以用 OpenAI 相容端點 (BYOK)。選好後可先測試連線。
        </p>

        <div className="space-y-2.5">
          {options.map((o) => {
            const active = selected === o.id
            const isByok = o.id === "openai"
            const disabled = !isByok && !o.available
            const Icon = isByok ? KeyRound : Cpu
            return (
              <button key={o.id} type="button" onClick={() => choose(o.id)}
                disabled={disabled}
                aria-pressed={active}
                className={`w-full text-left rounded-xl border p-4 flex items-start gap-3 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                  active ? "border-brand-500 bg-brand-50/60 ring-1 ring-brand-200"
                    : "border-slate-200 hover:bg-slate-50"
                } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}>
                <span className={`grid place-items-center w-9 h-9 rounded-lg shrink-0 ${active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500"}`}>
                  <Icon className="w-5 h-5" />
                </span>
                <span className="flex-1 min-w-0">
                  <span className="flex items-center gap-2">
                    <span className="font-medium text-slate-900">{o.label}</span>
                    {CLI_IDS.includes(o.id) && !o.available && (
                      <span className="text-xs text-slate-400">未偵測到</span>
                    )}
                  </span>
                  <span className="block text-sm text-slate-500 mt-0.5">{DESC[o.id] || ""}</span>
                </span>
              </button>
            )
          })}
        </div>

        {selectedKind === "byok" && (
          <div className="mt-4 space-y-2">
            <input value={byok.base_url} onChange={(e) => setByok((b) => ({ ...b, base_url: e.target.value }))}
              placeholder="Base URL，例如 https://api.deepseek.com/v1" aria-label="Base URL"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            <input value={byok.api_key} onChange={(e) => setByok((b) => ({ ...b, api_key: e.target.value }))}
              type="password" autoComplete="off" placeholder="API Key" aria-label="API Key"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            <input value={byok.model} onChange={(e) => setByok((b) => ({ ...b, model: e.target.value }))}
              placeholder="Model，例如 deepseek-chat / gpt-4o-mini" aria-label="Model"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
          </div>
        )}

        {result && (
          <div className={`mt-4 text-sm rounded-lg p-3 flex items-center gap-2 ${
            result.ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>
            {result.ok ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <XCircle className="w-4 h-4 shrink-0" />}
            {result.message}
          </div>
        )}

        <div className="mt-5 flex items-center gap-3">
          <Button variant="secondary" onClick={test} loading={testing}
            disabled={!selected || starting}
            icon={testing ? undefined : selectedKind === "byok" ? KeyRound : Cpu}>
            {testing ? "測試中…" : "測試連線"}
          </Button>
          <Button onClick={start} loading={starting} disabled={!selected || testing} icon={ArrowRight}>
            開始使用
          </Button>
          <button type="button" onClick={onSkip || onDone}
            className="ml-auto text-sm text-slate-400 hover:text-slate-600 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
            跳過
          </button>
        </div>
        {testing && (
          <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" />測試可能需要幾秒鐘。
          </p>
        )}
      </div>
    </div>
  )
}
