import { useEffect, useRef, useState } from "react"
import { Brand } from "../ui/Brand"
import { Button } from "../ui/Button"
import { Cpu, CheckCircle2, XCircle, Loader2, ArrowRight, KeyRound } from "../ui/icons"
import { newTaskId, stopTask } from "../lib/taskControl"
import {
  LOCAL_MODEL_PROVIDERS,
  withDetectedLocalModels,
  withLocalProviderDefaults,
} from "../lib/localModels"
import type { LocalModelForm, LocalModelProvider } from "../lib/localModels"

interface BackendOption { id: string; label: string; available: boolean; kind: string }
interface BackendData {
  options?: BackendOption[]
  current?: string
  byok?: { base_url?: string; model?: string; has_key?: boolean }
  local_models?: { provider?: LocalModelProvider; base_url?: string; model?: string; has_key?: boolean }
}

const ONBOARD_IDS = ["claude_cli", "codex_cli", "ollama", "openai"]
const CLI_IDS = ["claude_cli", "codex_cli"]

const DESC: Record<string, string> = {
  claude_cli: "使用本機 Claude Code CLI，不需要在本 App 內輸入 API key。",
  codex_cli: "使用本機 Codex CLI，不需要在本 App 內輸入 API key。",
  ollama: "使用 Ollama 或 llama.cpp 本機模型，適合免費、隱私優先的職缺排序與初步篩選。",
  openai: "使用 OpenAI 相容端點，適合 OpenAI、DeepSeek、Groq、OpenRouter、Ollama、LM Studio。",
}

export function Onboarding({ onDone, onSkip }: { onDone: () => void; onSkip?: () => void }) {
  const [options, setOptions] = useState<BackendOption[]>([])
  const [selected, setSelected] = useState("")
  const [byok, setByok] = useState({ base_url: "", api_key: "", model: "" })
  const [local, setLocal] = useState<LocalModelForm>({
    provider: "ollama",
    base_url: "http://127.0.0.1:11434/v1",
    api_key: "",
    model: "",
  })
  const [localChoices, setLocalChoices] = useState<string[]>([])
  const [localDetect, setLocalDetect] = useState<"loading" | { ok: boolean; msg: string } | undefined>()
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [starting, setStarting] = useState(false)
  const testRef = useRef<{ taskId: string; ctrl: AbortController } | null>(null)

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
        setLocal({
          provider: d.local_models?.provider || "ollama",
          base_url: d.local_models?.base_url || "http://127.0.0.1:11434/v1",
          api_key: "",
          model: d.local_models?.model || "",
        })
        setLocalChoices([])
        setLocalDetect(undefined)
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

  async function saveLocalIfNeeded() {
    if (selected !== "ollama") return true
    const r = await fetch("/api/backend/local-model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(local),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      setResult({ ok: false, message: d.error || "本機模型設定格式不正確。" })
      return false
    }
    return true
  }

  async function saveConfigIfNeeded() {
    return (await saveByokIfNeeded()) && (await saveLocalIfNeeded())
  }

  async function detectLocalModels() {
    setLocalDetect("loading")
    try {
      const r = await fetch("/api/backend/local-models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(local),
      })
      const d = await r.json()
      const models = Array.isArray(d.models) ? d.models : []
      setLocalChoices(models)
      setLocal((cur) => withDetectedLocalModels(cur, models))
      setLocalDetect({ ok: Boolean(d.ok), msg: d.message || (d.ok ? "偵測完成" : "偵測失敗") })
    } catch {
      setLocalChoices([])
      setLocalDetect({ ok: false, msg: "偵測失敗，請確認本機服務已啟動。" })
    }
  }

  async function test() {
    if (!selected) return
    const ctrl = new AbortController()
    const taskId = newTaskId("onboarding-test")
    testRef.current = { taskId, ctrl }
    setTesting(true)
    setResult(null)
    try {
      if (!(await saveConfigIfNeeded())) return
      const r = await fetch("/api/backend/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({ backend: selected, task_id: taskId }),
      })
      const d = await r.json()
      setResult({ ok: Boolean(d.ok), message: d.message || (d.ok ? "測試成功" : "測試失敗") })
    } catch (e) {
      if ((e as Error)?.name === "AbortError") {
        setResult({ ok: false, message: "已停止測試" })
        return
      }
      setResult({ ok: false, message: "連線發生問題，請確認伺服器是否啟動。" })
    } finally {
      if (testRef.current?.ctrl === ctrl) {
        testRef.current = null
        setTesting(false)
      }
    }
  }

  async function stopTest() {
    const current = testRef.current
    if (!current) return
    try {
      await stopTask(current.taskId)
    } catch {
      // 停止失敗時仍中止前端等待。
    } finally {
      current.ctrl.abort()
      testRef.current = null
      setTesting(false)
      setResult({ ok: false, message: "已停止測試" })
    }
  }

  async function start() {
    if (!selected) return
    setStarting(true)
    try {
      if (!(await saveConfigIfNeeded())) return
      const r = await fetch("/api/backend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ backend: selected }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        setResult({ ok: false, message: d.error || "AI 後端套用失敗，請重新選擇。" })
        return
      }
      onDone()
    } finally {
      setStarting(false)
    }
  }

  const selectedKind = selected === "openai" ? "byok" : selected === "ollama" ? "local" : "cli"
  const modelChoices = local.model && !localChoices.includes(local.model)
    ? [local.model, ...localChoices]
    : localChoices

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm grid place-items-center p-4">
      <div className="w-full max-w-lg bg-white rounded-xl2 shadow-cardHover p-6 animate-fade-in-up">
        <div className="mb-5"><Brand /></div>
        <h1 className="text-lg font-bold text-slate-900 mb-1">選擇 AI 後端</h1>
        <p className="text-sm text-slate-500 mb-4">
          可以使用本機 Claude/Codex CLI、本機模型，或 OpenAI 相容端點 (BYOK)。選好後可先測試連線。
        </p>

        <div className="space-y-2.5">
          {options.map((o) => {
            const active = selected === o.id
            const isByok = o.id === "openai"
            const disabled = CLI_IDS.includes(o.id) && !o.available
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

        {selectedKind === "local" && (
          <div className="mt-4 space-y-2">
            <select value={local.provider}
              onChange={(e) => {
                setLocal((cur) => withLocalProviderDefaults(e.target.value as LocalModelProvider, cur))
                setLocalChoices([])
                setLocalDetect(undefined)
              }}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200">
              {LOCAL_MODEL_PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <input value={local.base_url} onChange={(e) => {
              setLocal((b) => ({ ...b, base_url: e.target.value }))
              setLocalChoices([])
              setLocalDetect(undefined)
            }}
              placeholder="Base URL，例如 http://127.0.0.1:11434/v1" aria-label="Local model base URL"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            <div className="flex items-center gap-2">
              {modelChoices.length > 0 ? (
                <select value={local.model} onChange={(e) => setLocal((b) => ({ ...b, model: e.target.value }))}
                  aria-label="Local model"
                  className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200">
                  {modelChoices.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input value={local.model} onChange={(e) => setLocal((b) => ({ ...b, model: e.target.value }))}
                  placeholder="Model，例如 qwen3:8b / llama3.1:8b" aria-label="Local model"
                  className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
              )}
              <button type="button" onClick={detectLocalModels} disabled={localDetect === "loading"}
                className="text-sm border border-slate-300 rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                {localDetect === "loading" ? "偵測中" : "重新偵測"}
              </button>
            </div>
            <input value={local.api_key} onChange={(e) => setLocal((b) => ({ ...b, api_key: e.target.value }))}
              type="password" autoComplete="off" placeholder="API Key（多數本機服務可留空）" aria-label="Local model API key"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            {localDetect && localDetect !== "loading" && (
              <p className={`text-xs ${localDetect.ok ? "text-emerald-600" : "text-rose-600"}`}>{localDetect.msg}</p>
            )}
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
          {testing && <Button variant="danger" onClick={stopTest} icon={XCircle}>停止</Button>}
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
