import { useState } from "react"
import { useBackend, CLI_AGENTS, modelLabel } from "../lib/useBackend"
import { ExecutionSettings } from "./ExecutionSettings"
import { Cpu, ChevronDown, KeyRound, Settings2, CircleDot, Circle } from "../ui/icons"

// 右上角後端控制台（仿 open-design）：模式（本機 CLI / 自備 Key）→ 代理 → 模型策略。
// 連線測試在「執行設定」面板、與選模型分開。anthropic 是有效後端但不在此露出。
export function BackendSelector({ refreshKey = 0 }: { refreshKey?: number }) {
  const be = useBackend(refreshKey)
  const [open, setOpen] = useState(false)
  const [settings, setSettings] = useState(false)
  const [mode, setMode] = useState<"cli" | "byok">("cli")
  const [byok, setByok] = useState({ base_url: "", api_key: "", model: "" })

  function toggle() {
    const next = !open
    setOpen(next)
    if (next && be.data) {
      const kind = be.data.options.find((o) => o.id === be.data!.current)?.kind
      setMode(kind === "byok" ? "byok" : "cli")
      setByok({ base_url: be.data.byok.base_url || "", api_key: "", model: be.data.byok.model || "" })
    }
  }

  if (!be.data) return null
  const d = be.data
  const cur = d.options.find((o) => o.id === d.current)
  const activeCli = CLI_AGENTS.find((a) => a.id === d.current)?.id || ""
  const pill = cur?.kind === "byok"
    ? `自備 Key · ${d.byok.model || "未設定"}`
    : `本機 CLI · ${CLI_AGENTS.find((a) => a.id === d.current)?.name || cur?.label || "—"} · ${modelLabel(d.cli_models[d.current]?.current)}`

  return (
    <div className="relative no-print">
      <button type="button" onClick={toggle} aria-expanded={open}
        title="切換 AI 後端：本機 CLI 訂閱或自備 Key（OpenAI 相容）。"
        className={`inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white pl-3 pr-2 py-1.5 text-xs text-slate-700 shadow-card hover:bg-slate-50 ${be.busy ? "opacity-60" : ""}`}>
        <Cpu className="w-4 h-4 text-brand-500" />
        <span className="font-medium text-slate-800">{pill}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 mt-2 w-[20rem] max-w-[calc(100vw-2rem)] z-50 rounded-xl border border-slate-200 bg-white shadow-cardHover p-3 animate-fade-in-up">
            {/* 模式 */}
            <p className="text-xs font-medium text-slate-400 mb-1.5">模式</p>
            <div className="flex gap-1 bg-slate-100 rounded-lg p-1 mb-3">
              {([["cli", "本機 CLI"], ["byok", "自備 Key"]] as const).map(([id, label]) => (
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
