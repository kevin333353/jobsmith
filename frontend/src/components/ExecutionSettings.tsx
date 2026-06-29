import { useEffect, useState } from "react"
import { useBackend, CLI_AGENTS } from "../lib/useBackend"
import type { ByokForm } from "../lib/useBackend"
import {
  LOCAL_MODEL_PROVIDERS,
  withDetectedLocalModels,
  withLocalProviderDefaults,
} from "../lib/localModels"
import type { LocalModelForm, LocalModelProvider } from "../lib/localModels"
import { Cpu, KeyRound, RefreshCw, CheckCircle2, XCircle, Loader2, X, CircleDot, Circle } from "../ui/icons"

// 「執行模式與模型」設定面板（仿 open-design）：本機 CLI / BYOK 兩頁。
// 本機 CLI：掃描 PATH 偵測各 CLI、選代理、選模型策略、測試。
export function ExecutionSettings({ onClose }: { onClose: () => void }) {
  const be = useBackend()
  const [tab, setTab] = useState<"cli" | "local" | "byok">("cli")
  const [byok, setByok] = useState<ByokForm>({ base_url: "", api_key: "", model: "" })
  const [local, setLocal] = useState<LocalModelForm>({
    provider: "ollama",
    base_url: "http://127.0.0.1:11434/v1",
    api_key: "",
    model: "",
  })
  const [localChoices, setLocalChoices] = useState<string[]>([])
  const [localDetect, setLocalDetect] = useState<"loading" | { ok: boolean; msg: string } | undefined>()
  const [initFrom, setInitFrom] = useState<string | null>(null)

  // 資料載入後，把分頁與 BYOK 草稿同步成目前後端狀態（只同步一次，避免覆蓋使用者輸入）。
  useEffect(() => {
    if (!be.data || initFrom === be.data.current) return
    const kind = be.data.options.find((o) => o.id === be.data!.current)?.kind
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTab(kind === "byok" ? "byok" : kind === "local" ? "local" : "cli")
    setByok({ base_url: be.data.byok.base_url || "", api_key: "", model: be.data.byok.model || "" })
    setLocal({
      provider: be.data.local_models.provider || "ollama",
      base_url: be.data.local_models.base_url || "http://127.0.0.1:11434/v1",
      api_key: "",
      model: be.data.local_models.model || "",
    })
    setLocalChoices([])
    setLocalDetect(undefined)
    setInitFrom(be.data.current)
  }, [be.data, initFrom])

  if (!be.data) return null
  const d = be.data
  const activeCli = CLI_AGENTS.find((a) => a.id === d.current)?.id || ""
  const cliTestId = activeCli || CLI_AGENTS.find((a) => d.options.find((o) => o.id === a.id)?.available)?.id || "claude_cli"
  const modelChoices = local.model && !localChoices.includes(local.model)
    ? [local.model, ...localChoices]
    : localChoices
  const tabBtn = (id: "cli" | "local" | "byok") =>
    `flex-1 text-sm font-medium py-2 rounded-lg transition ${
      tab === id ? "bg-white text-slate-900 shadow-card" : "text-slate-500 hover:text-slate-700"}`

  async function detectLocalModels() {
    setLocalDetect("loading")
    try {
      const result = await be.detectLocalModels(local)
      setLocalChoices(result.models || [])
      setLocal((cur) => withDetectedLocalModels(cur, result.models || []))
      setLocalDetect({ ok: result.ok, msg: result.message || (result.ok ? "偵測完成" : "偵測失敗") })
    } catch {
      setLocalChoices([])
      setLocalDetect({ ok: false, msg: "偵測失敗，請確認本機服務已啟動。" })
    }
  }

  return (
    <div className="fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-sm grid place-items-center p-4" onClick={onClose}>
      <div className="w-full max-w-2xl bg-white rounded-xl2 shadow-cardHover p-6 animate-fade-in-up" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-1">
          <h1 className="text-lg font-bold text-slate-900">執行模式與模型</h1>
          <button type="button" onClick={onClose} aria-label="關閉"
            className="text-slate-400 hover:text-slate-600 rounded p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-slate-500 mb-4">在本機 CLI、本機模型與 BYOK 之間選擇。金鑰只寫進你本機的 .env，不會外傳。</p>

        <div className="flex gap-1 bg-slate-100 rounded-xl p-1 mb-4">
          <button type="button" onClick={() => setTab("cli")} className={tabBtn("cli")}>本機 CLI</button>
          <button type="button" onClick={() => setTab("local")} className={tabBtn("local")}>本機模型</button>
          <button type="button" onClick={() => setTab("byok")} className={tabBtn("byok")}>BYOK</button>
        </div>

        {tab === "cli" && (
          <div>
            <div className="flex items-start justify-between gap-3 mb-3">
              <div>
                <p className="font-semibold text-sm text-slate-800">本機 CLI</p>
                <p className="text-xs text-slate-500">透過掃描 PATH 自動偵測，選擇你希望使用的 CLI。</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {be.tests[cliTestId] === "loading" ? (
                  <button type="button" onClick={() => be.stopTest(cliTestId)}
                    className="text-xs border border-rose-200 bg-rose-50 rounded-lg px-3 py-1.5 text-rose-700 hover:bg-rose-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300">
                    停止
                  </button>
                ) : (
                  <button type="button" onClick={() => be.runTest(cliTestId)} disabled={be.busy}
                    className="text-xs border border-slate-300 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                    測試
                  </button>
                )}
                <button type="button" onClick={() => be.reload()} disabled={be.busy}
                  className="inline-flex items-center gap-1 text-xs border border-slate-300 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                  <RefreshCw className="w-3.5 h-3.5" />重新掃描
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {CLI_AGENTS.map((a) => {
                const o = d.options.find((x) => x.id === a.id)
                const active = d.current === a.id
                const avail = Boolean(o?.available)
                return (
                  <button key={a.id} type="button" onClick={() => avail && be.activate(a.id)} disabled={!avail || be.busy}
                    className={`text-left rounded-xl border p-3 flex items-center gap-3 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                      active ? "border-brand-400 bg-brand-50/60 ring-1 ring-brand-200" : "border-slate-200 hover:bg-slate-50"
                    } ${avail ? "" : "opacity-60"}`}>
                    <span className={`grid place-items-center w-9 h-9 rounded-lg shrink-0 ${active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500"}`}>
                      <Cpu className="w-5 h-5" />
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="font-medium text-sm text-slate-900 block truncate">{a.name}</span>
                      <span className="text-xs text-slate-400 block truncate">{avail ? (o?.version || "已安裝") : "未安裝"}</span>
                    </span>
                    {active ? <CircleDot className="w-4 h-4 text-brand-600 shrink-0" /> : <Circle className="w-4 h-4 text-slate-300 shrink-0" />}
                  </button>
                )
              })}
            </div>

            <div className="mt-3 flex items-center gap-2">
              <span className="text-sm text-slate-600">模型策略</span>
              <select value={d.cli_models[cliTestId]?.current || "auto"} disabled={be.busy}
                onChange={(e) => be.setModel(cliTestId, e.target.value)}
                className="flex-1 border border-slate-300 rounded-lg px-2.5 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-50">
                {(d.cli_models[cliTestId]?.choices || ["auto"]).map((c) => (
                  <option key={c} value={c}>{c === "auto" ? "預設策略" : c}</option>
                ))}
              </select>
            </div>
            <TestLine t={be.tests[cliTestId]} />
          </div>
        )}

        {tab === "local" && (
          <div className="space-y-2">
            <p className="text-xs text-slate-500">使用 Ollama 或 llama.cpp server 的 OpenAI 相容端點。適合免費、本機、隱私優先的職缺排序與初步篩選。</p>
            <select value={local.provider}
              onChange={(e) => setLocal((cur) => withLocalProviderDefaults(e.target.value as LocalModelProvider, cur))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200">
              {LOCAL_MODEL_PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <input value={local.base_url} onChange={(e) => setLocal((b) => ({ ...b, base_url: e.target.value }))}
              placeholder="Base URL（Ollama：http://127.0.0.1:11434/v1）" aria-label="Local model base URL"
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
                  placeholder="Model（例：qwen3:8b / llama3.1:8b / local-model）" aria-label="Local model"
                  className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
              )}
              <button type="button" onClick={detectLocalModels} disabled={localDetect === "loading"}
                className="text-sm border border-slate-300 rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                {localDetect === "loading" ? "偵測中" : "重新偵測"}
              </button>
            </div>
            <input value={local.api_key} onChange={(e) => setLocal((b) => ({ ...b, api_key: e.target.value }))}
              type="password" autoComplete="off"
              placeholder={d.local_models.has_key ? "API Key（已設定，留空＝不變更）" : "API Key（多數本機服務可留空）"} aria-label="Local model API key"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            <div className="flex items-center gap-2 pt-1">
              {be.tests.ollama === "loading" ? (
                <button type="button" onClick={() => be.stopTest("ollama")}
                  className="text-sm border border-rose-200 bg-rose-50 rounded-lg px-3 py-1.5 text-rose-700 hover:bg-rose-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300">
                  停止
                </button>
              ) : (
                <button type="button" onClick={async () => { await be.saveLocalModel(local, false); be.runTest("ollama") }} disabled={be.busy}
                  className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                  測試
                </button>
              )}
              <button type="button" onClick={() => be.saveLocalModel(local, true)} disabled={be.busy}
                className="inline-flex items-center gap-1.5 text-sm bg-brand-600 text-white rounded-lg px-3 py-1.5 hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                <Cpu className="w-4 h-4" />儲存並啟用
              </button>
            </div>
            <TestLine t={localDetect} />
            <TestLine t={be.tests.ollama} />
          </div>
        )}

        {tab === "byok" && (
          <div className="space-y-2">
            <p className="text-xs text-slate-500">填入任何 OpenAI 相容端點（OpenAI / DeepSeek / Gemini / Groq / OpenRouter / Ollama / LM Studio / vLLM…）。</p>
            <input value={byok.base_url} onChange={(e) => setByok((b) => ({ ...b, base_url: e.target.value }))}
              placeholder="Base URL（例：https://api.deepseek.com/v1）" aria-label="Base URL"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            <input value={byok.api_key} onChange={(e) => setByok((b) => ({ ...b, api_key: e.target.value }))}
              type="password" autoComplete="off"
              placeholder={d.byok.has_key ? "API Key（已設定，留空＝不變更）" : "API Key"} aria-label="API Key"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            <input value={byok.model} onChange={(e) => setByok((b) => ({ ...b, model: e.target.value }))}
              placeholder="Model（例：deepseek-chat / gpt-4o-mini）" aria-label="Model"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200" />
            <div className="flex items-center gap-2 pt-1">
              {be.tests.openai === "loading" ? (
                <button type="button" onClick={() => be.stopTest("openai")}
                  className="text-sm border border-rose-200 bg-rose-50 rounded-lg px-3 py-1.5 text-rose-700 hover:bg-rose-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300">
                  停止
                </button>
              ) : (
                <button type="button" onClick={async () => { await be.saveByok(byok, false); be.runTest("openai") }} disabled={be.busy}
                  className="text-sm border border-slate-300 rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                  測試
                </button>
              )}
              <button type="button" onClick={() => be.saveByok(byok, true)} disabled={be.busy}
                className="inline-flex items-center gap-1.5 text-sm bg-brand-600 text-white rounded-lg px-3 py-1.5 hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50">
                <KeyRound className="w-4 h-4" />儲存並啟用
              </button>
            </div>
            <TestLine t={be.tests.openai} />
          </div>
        )}
      </div>
    </div>
  )
}

function TestLine({ t }: { t: "loading" | { ok: boolean; msg: string } | undefined }) {
  if (!t) return null
  return (
    <div className={`mt-3 text-sm inline-flex items-center gap-1.5 ${
      t === "loading" ? "text-slate-500" : t.ok ? "text-emerald-600" : "text-rose-600"}`}>
      {t === "loading" ? <Loader2 className="w-4 h-4 animate-spin" />
        : t.ok ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
      {t === "loading" ? "測試中…" : t.msg}
    </div>
  )
}
