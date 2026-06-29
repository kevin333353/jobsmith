import { useState } from "react"
import { useBackend, CLI_AGENTS, modelLabel } from "../lib/useBackend"
import { ExecutionSettings } from "./ExecutionSettings"
import {
  LOCAL_MODEL_PROVIDERS,
  localProviderLabel,
  withDetectedLocalModels,
  withLocalProviderDefaults,
} from "../lib/localModels"
import type { LocalModelForm, LocalModelProvider } from "../lib/localModels"
import { Cpu, ChevronDown, KeyRound, Settings2, CircleDot, Circle } from "../ui/icons"

// 右上角後端控制台（仿 open-design）：模式（本機 CLI / 自備 Key）→ 代理 → 模型策略。
// 連線測試在「執行設定」面板、與選模型分開。anthropic 是有效後端但不在此露出。
export function BackendSelector({ refreshKey = 0 }: { refreshKey?: number }) {
  const be = useBackend(refreshKey)
  const [open, setOpen] = useState(false)
  const [settings, setSettings] = useState(false)
  const [mode, setMode] = useState<"cli" | "local" | "byok">("cli")
  const [byok, setByok] = useState({ base_url: "", api_key: "", model: "" })
  const [local, setLocal] = useState<LocalModelForm>({
    provider: "ollama",
    base_url: "http://127.0.0.1:11434/v1",
    api_key: "",
    model: "",
  })
  const [localChoices, setLocalChoices] = useState<string[]>([])
  const [localDetect, setLocalDetect] = useState<"loading" | { ok: boolean; msg: string } | undefined>()

  function toggle() {
    const next = !open
    setOpen(next)
    if (next && be.data) {
      const kind = be.data.options.find((o) => o.id === be.data!.current)?.kind
      setMode(kind === "byok" ? "byok" : kind === "local" ? "local" : "cli")
      setByok({ base_url: be.data.byok.base_url || "", api_key: "", model: be.data.byok.model || "" })
      setLocal({
        provider: be.data.local_models.provider || "ollama",
        base_url: be.data.local_models.base_url || "http://127.0.0.1:11434/v1",
        api_key: "",
        model: be.data.local_models.model || "",
      })
      setLocalChoices([])
      setLocalDetect(undefined)
    }
  }

  if (!be.data) return null
  const d = be.data
  const cur = d.options.find((o) => o.id === d.current)
  const activeCli = CLI_AGENTS.find((a) => a.id === d.current)?.id || ""
  const modelChoices = local.model && !localChoices.includes(local.model)
    ? [local.model, ...localChoices]
    : localChoices
  const pill = cur?.kind === "byok"
    ? `自備 Key · ${d.byok.model || "未設定"}`
    : cur?.kind === "local"
      ? `本機模型 · ${localProviderLabel(d.local_models.provider)} · ${d.local_models.model || "未設定"}`
      : `本機 CLI · ${CLI_AGENTS.find((a) => a.id === d.current)?.name || cur?.label || "—"} · ${modelLabel(d.cli_models[d.current]?.current)}`

  async function detectLocalModels() {
    setLocalDetect("loading")
    try {
      const result = await be.detectLocalModels(local)
      setLocalChoices(result.models || [])
      setLocal((curLocal) => withDetectedLocalModels(curLocal, result.models || []))
      setLocalDetect({ ok: result.ok, msg: result.message || (result.ok ? "偵測完成" : "偵測失敗") })
    } catch {
      setLocalChoices([])
      setLocalDetect({ ok: false, msg: "偵測失敗，請確認本機服務已啟動。" })
    }
  }

  return (
    <div className="relative no-print">
      <button type="button" onClick={toggle} aria-expanded={open}
        title="切換 AI 後端：本機 CLI、本機模型或自備 Key（OpenAI 相容）。"
        className={`inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white pl-3 pr-2 py-1.5 text-xs text-slate-700 shadow-card hover:bg-slate-50 ${be.busy ? "opacity-60" : ""}`}>
        <Cpu className="w-4 h-4 text-brand-500" />
        <span className="font-medium text-slate-800">{pill}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 mt-2 w-[23rem] max-w-[calc(100vw-2rem)] z-50 rounded-xl border border-slate-200 bg-white shadow-cardHover p-3 animate-fade-in-up">
            {/* 模式 */}
            <p className="text-xs font-medium text-slate-400 mb-1.5">模式</p>
            <div className="flex gap-1 bg-slate-100 rounded-lg p-1 mb-3">
              {([["cli", "本機 CLI"], ["local", "本機模型"], ["byok", "自備 Key"]] as const).map(([id, label]) => (
                <button key={id} type="button" onClick={() => setMode(id)}
                  className={`flex-1 text-sm font-medium py-1.5 rounded-md transition ${
                    mode === id ? "bg-white text-slate-900 shadow-card" : "text-slate-500 hover:text-slate-700"}`}>
                  {label}
                </button>
              ))}
            </div>

            {mode === "cli" && (
              <>
                <p className="text-xs font-medium text-slate-400 mb-1.5">代理</p>
                <div className="grid grid-cols-1 gap-1.5 mb-3">
                  {CLI_AGENTS.map((a) => {
                    const o = d.options.find((x) => x.id === a.id)
                    const active = d.current === a.id
                    const avail = Boolean(o?.available)
                    return (
                      <button key={a.id} type="button" onClick={() => avail && be.activate(a.id)} disabled={!avail || be.busy}
                        className={`text-left rounded-lg border p-2.5 flex items-center gap-2.5 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                          active ? "border-brand-400 bg-brand-50/60 ring-1 ring-brand-200" : "border-slate-200 hover:bg-slate-50"
                        } ${avail ? "" : "opacity-60"}`}>
                        <Cpu className={`w-4 h-4 shrink-0 ${active ? "text-brand-600" : "text-slate-400"}`} />
                        <span className="flex-1 min-w-0">
                          <span className="text-sm font-medium text-slate-800 block truncate">{a.name}</span>
                          {!avail && <span className="text-xs text-slate-400">未偵測到</span>}
                        </span>
                        {active ? <CircleDot className="w-4 h-4 text-brand-600 shrink-0" /> : <Circle className="w-4 h-4 text-slate-300 shrink-0" />}
                      </button>
                    )
                  })}
                </div>
                <p className="text-xs font-medium text-slate-400 mb-1.5">模型策略</p>
                {activeCli ? (
                  <select value={d.cli_models[activeCli]?.current || "auto"} disabled={be.busy}
                    onChange={(e) => be.setModel(activeCli, e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50">
                    {(d.cli_models[activeCli]?.choices || ["auto"]).map((c) => (
                      <option key={c} value={c}>{c === "auto" ? "預設策略" : c}</option>
                    ))}
                  </select>
                ) : (
                  <p className="text-xs text-slate-400">先選一個 CLI 代理。</p>
                )}
              </>
            )}

            {mode === "local" && (
              <div className="space-y-1.5 mb-1">
                <select value={local.provider}
                  onChange={(e) => {
                    setLocal((curLocal) => withLocalProviderDefaults(e.target.value as LocalModelProvider, curLocal))
                    setLocalChoices([])
                    setLocalDetect(undefined)
                  }}
                  className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-brand-200">
                  {LOCAL_MODEL_PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>{p.label}</option>
                  ))}
                </select>
                <input value={local.base_url} onChange={(e) => {
                  setLocal((b) => ({ ...b, base_url: e.target.value }))
                  setLocalChoices([])
                  setLocalDetect(undefined)
                }}
                  placeholder="Base URL（例：http://127.0.0.1:11434/v1）" aria-label="Local model base URL"
                  className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-200" />
                <div className="flex items-center gap-1.5">
                  {modelChoices.length > 0 ? (
                    <select value={local.model} onChange={(e) => setLocal((b) => ({ ...b, model: e.target.value }))}
                      aria-label="Local model"
                      className="flex-1 min-w-0 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-brand-200">
                      {modelChoices.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                  ) : (
                    <input value={local.model} onChange={(e) => setLocal((b) => ({ ...b, model: e.target.value }))}
                      placeholder="Model（例：qwen3:8b）" aria-label="Local model"
                      className="flex-1 min-w-0 border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-200" />
                  )}
                  <button type="button" onClick={detectLocalModels} disabled={localDetect === "loading"}
                    className="shrink-0 text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                    {localDetect === "loading" ? "偵測中" : "偵測"}
                  </button>
                </div>
                <input value={local.api_key} onChange={(e) => setLocal((b) => ({ ...b, api_key: e.target.value }))}
                  type="password" autoComplete="off"
                  placeholder={d.local_models.has_key ? "API Key（已設定，留空＝不變更）" : "API Key（可留空）"} aria-label="Local model API key"
                  className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-200" />
                {localDetect && localDetect !== "loading" && (
                  <p className={`text-xs ${localDetect.ok ? "text-emerald-600" : "text-rose-600"}`}>{localDetect.msg}</p>
                )}
                <button type="button" onClick={() => be.saveLocalModel(local, true)} disabled={be.busy}
                  className="w-full inline-flex items-center justify-center gap-1.5 text-sm bg-brand-600 text-white rounded-lg px-3 py-1.5 hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                  <Cpu className="w-4 h-4" />儲存並啟用
                </button>
              </div>
            )}

            {mode === "byok" && (
              <div className="space-y-1.5 mb-1">
                <input value={byok.base_url} onChange={(e) => setByok((b) => ({ ...b, base_url: e.target.value }))}
                  placeholder="Base URL（例：https://api.deepseek.com/v1）" aria-label="Base URL"
                  className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-200" />
                <input value={byok.api_key} onChange={(e) => setByok((b) => ({ ...b, api_key: e.target.value }))}
                  type="password" autoComplete="off"
                  placeholder={d.byok.has_key ? "API Key（已設定，留空＝不變更）" : "API Key"} aria-label="API Key"
                  className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-200" />
                <input value={byok.model} onChange={(e) => setByok((b) => ({ ...b, model: e.target.value }))}
                  placeholder="Model（例：deepseek-chat / gpt-4o-mini）" aria-label="Model"
                  className="w-full border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-200" />
                <button type="button" onClick={() => be.saveByok(byok, true)} disabled={be.busy}
                  className="w-full inline-flex items-center justify-center gap-1.5 text-sm bg-brand-600 text-white rounded-lg px-3 py-1.5 hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                  <KeyRound className="w-4 h-4" />儲存並啟用
                </button>
              </div>
            )}

            <button type="button" onClick={() => { setOpen(false); setSettings(true) }}
              className="mt-3 w-full inline-flex items-center gap-2 text-xs text-slate-500 hover:text-brand-600 rounded px-1 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
              <Settings2 className="w-4 h-4" />開啟執行設定（掃描、測試、版本）
            </button>
          </div>
        </>
      )}

      {settings && <ExecutionSettings onClose={() => { setSettings(false); be.reload() }} />}
    </div>
  )
}
