import { useEffect, useRef, useState } from "react"
import type { LocalModelForm, LocalModelProvider } from "./localModels"
import { newTaskId, stopTask } from "./taskControl"

// 後端控制台共用資料層：右上角 popover 與「執行設定」面板都用這個 hook。
export interface BackendOption { id: string; label: string; available: boolean; kind: string; version?: string }
export interface CliModel { choices: string[]; current: string }
export interface ByokCfg { base_url: string; model: string; has_key: boolean }
export interface LocalModelCfg { provider: LocalModelProvider; base_url: string; model: string; has_key: boolean }
export interface LocalModelDetectResult { ok: boolean; models: string[]; message: string }
export interface BackendData {
  current: string
  options: BackendOption[]
  cli_models: Record<string, CliModel>
  byok: ByokCfg
  local_models: LocalModelCfg
}
export type TestState = "loading" | { ok: boolean; msg: string } | undefined
export interface ByokForm { base_url: string; api_key: string; model: string }

function postJSON(url: string, body: unknown, signal?: AbortSignal) {
  return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal })
}

export function useBackend(reloadKey = 0) {
  const [data, setData] = useState<BackendData | null>(null)
  const [busy, setBusy] = useState(false)
  const [tests, setTests] = useState<Record<string, TestState>>({})
  const testTasksRef = useRef<Record<string, { taskId: string; ctrl: AbortController }>>({})

  async function reload(): Promise<BackendData | null> {
    try {
      const d: BackendData = await (await fetch("/api/backend")).json()
      setData(d)
      return d
    } catch { return null }
  }
  useEffect(() => {
    // 初次載入後端清單；reload 在 await 之後才 setState（非渲染期同步），是 effect 正當用途。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload()
  }, [reloadKey])

  async function activate(id: string) {
    setBusy(true)
    try {
      const r = await postJSON("/api/backend", { backend: id })
      if (r.ok) setData((d) => (d ? { ...d, current: id } : d))
    } finally { setBusy(false) }
  }

  async function setModel(backend: string, model: string) {
    setData((d) => (d ? { ...d, cli_models: { ...d.cli_models, [backend]: { ...d.cli_models[backend], current: model } } } : d))
    await postJSON("/api/backend/model", { backend, model })
  }

  async function saveByok(cfg: ByokForm, activateAfter: boolean) {
    setBusy(true)
    try {
      await postJSON("/api/backend/byok", cfg)
      if (activateAfter) await activate("openai")
      await reload()
    } finally { setBusy(false) }
  }

  async function saveLocalModel(cfg: LocalModelForm, activateAfter: boolean) {
    setBusy(true)
    try {
      await postJSON("/api/backend/local-model", cfg)
      if (activateAfter) await activate("ollama")
      await reload()
    } finally { setBusy(false) }
  }

  async function detectLocalModels(cfg: LocalModelForm): Promise<LocalModelDetectResult> {
    const r = await postJSON("/api/backend/local-models", cfg)
    return await r.json()
  }

  async function runTest(id: string) {
    const previous = testTasksRef.current[id]
    if (previous) {
      void stopTask(previous.taskId).catch(() => undefined)
      previous.ctrl.abort()
    }
    const ctrl = new AbortController()
    const taskId = newTaskId(`backend-${id}`)
    testTasksRef.current[id] = { taskId, ctrl }
    setTests((t) => ({ ...t, [id]: "loading" }))
    try {
      const d = await (await postJSON("/api/backend/test", { backend: id, task_id: taskId }, ctrl.signal)).json()
      setTests((t) => ({ ...t, [id]: { ok: Boolean(d.ok), msg: d.message || (d.ok ? "連線成功" : "連線失敗") } }))
    } catch (e) {
      if ((e as Error)?.name === "AbortError") {
        setTests((t) => ({ ...t, [id]: { ok: false, msg: "已停止測試" } }))
        return
      }
      setTests((t) => ({ ...t, [id]: { ok: false, msg: "連線發生問題，請確認伺服器已啟動。" } }))
    } finally {
      if (testTasksRef.current[id]?.ctrl === ctrl) delete testTasksRef.current[id]
    }
  }

  async function stopTest(id: string) {
    const current = testTasksRef.current[id]
    if (!current) return
    try {
      await stopTask(current.taskId)
    } catch {
      // 停止失敗時仍中止前端等待。
    } finally {
      current.ctrl.abort()
      delete testTasksRef.current[id]
      setTests((t) => ({ ...t, [id]: { ok: false, msg: "已停止測試" } }))
    }
  }

  return { data, busy, tests, reload, activate, setModel, saveByok, saveLocalModel, detectLocalModels, runTest, stopTest }
}

// CLI 代理清單（目前支援的本機 CLI）。顯示名與後端 id 對應。
export const CLI_AGENTS: { id: string; name: string }[] = [
  { id: "claude_cli", name: "Claude Code" },
  { id: "codex_cli", name: "Codex CLI" },
]

export function modelLabel(m: string | undefined): string {
  return !m || m === "auto" ? "預設" : m
}
