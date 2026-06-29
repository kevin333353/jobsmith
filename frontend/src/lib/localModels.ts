export type LocalModelProvider = "ollama" | "llama_cpp" | "custom"

export interface LocalModelForm {
  provider: LocalModelProvider
  base_url: string
  api_key: string
  model: string
}

export const LOCAL_MODEL_PROVIDERS: { id: LocalModelProvider; label: string; defaultBaseUrl: string }[] = [
  { id: "ollama", label: "Ollama", defaultBaseUrl: "http://127.0.0.1:11434/v1" },
  { id: "llama_cpp", label: "llama.cpp", defaultBaseUrl: "http://127.0.0.1:8080/v1" },
  { id: "custom", label: "自訂", defaultBaseUrl: "" },
]

export function localProviderLabel(provider: string | undefined): string {
  return LOCAL_MODEL_PROVIDERS.find((p) => p.id === provider)?.label || "本機模型"
}

function defaultBaseUrl(provider: LocalModelProvider): string {
  return LOCAL_MODEL_PROVIDERS.find((p) => p.id === provider)?.defaultBaseUrl || ""
}

function knownDefaultBaseUrls(): Set<string> {
  return new Set(LOCAL_MODEL_PROVIDERS.map((p) => p.defaultBaseUrl).filter(Boolean))
}

export function withLocalProviderDefaults(provider: LocalModelProvider, current: LocalModelForm): LocalModelForm {
  const nextDefault = defaultBaseUrl(provider)
  const shouldReplaceBaseUrl =
    !current.base_url ||
    knownDefaultBaseUrls().has(current.base_url) ||
    provider === "custom"

  return {
    ...current,
    provider,
    base_url: shouldReplaceBaseUrl ? (nextDefault || current.base_url) : current.base_url,
  }
}

export function withDetectedLocalModels(current: LocalModelForm, models: string[]): LocalModelForm {
  const first = models.find((m) => m.trim())
  if (current.model || !first) return current
  return { ...current, model: first }
}
