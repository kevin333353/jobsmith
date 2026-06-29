import test from "node:test"
import assert from "node:assert/strict"

import {
  LOCAL_MODEL_PROVIDERS,
  localProviderLabel,
  withDetectedLocalModels,
  withLocalProviderDefaults,
} from "../src/lib/localModels.ts"

test("local model providers expose Ollama and llama.cpp choices", () => {
  assert.deepEqual(LOCAL_MODEL_PROVIDERS.map((p) => p.id), ["ollama", "llama_cpp", "custom"])
  assert.equal(localProviderLabel("ollama"), "Ollama")
  assert.equal(localProviderLabel("llama_cpp"), "llama.cpp")
})

test("switching between local presets fills the expected default base URL", () => {
  const fromOllama = withLocalProviderDefaults("llama_cpp", {
    provider: "ollama",
    base_url: "http://127.0.0.1:11434/v1",
    api_key: "",
    model: "qwen3:8b",
  })

  assert.equal(fromOllama.provider, "llama_cpp")
  assert.equal(fromOllama.base_url, "http://127.0.0.1:8080/v1")
  assert.equal(fromOllama.model, "qwen3:8b")
})

test("custom local endpoint keeps the user's base URL", () => {
  const custom = withLocalProviderDefaults("custom", {
    provider: "ollama",
    base_url: "http://localhost:9999/v1",
    api_key: "",
    model: "local-model",
  })

  assert.equal(custom.provider, "custom")
  assert.equal(custom.base_url, "http://localhost:9999/v1")
})

test("detected local models fill an empty model without replacing an existing choice", () => {
  const blank = withDetectedLocalModels({
    provider: "ollama",
    base_url: "http://127.0.0.1:11434/v1",
    api_key: "",
    model: "",
  }, ["qwen3:8b", "llama3.1:8b"])

  assert.equal(blank.model, "qwen3:8b")

  const chosen = withDetectedLocalModels({
    provider: "ollama",
    base_url: "http://127.0.0.1:11434/v1",
    api_key: "",
    model: "llama3.1:8b",
  }, ["qwen3:8b", "llama3.1:8b"])

  assert.equal(chosen.model, "llama3.1:8b")
})
