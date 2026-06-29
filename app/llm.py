"""依 LLM_BACKEND 建立 LLM（介面一致：.with_structured_output(...).invoke(...)）。

支援後端：
- claude_cli / codex_cli：本機 CLI 訂閱（免 API key、不吃額度）——使用者可在 UI 切換（主要）。
- anthropic：API key（雲端/部署用，可選）。
"""
from app import settings
from app.llm_errors import ensure_structured_result, normalize_structured_exception
from app.settings import get_model


class _FriendlyStructured:
    def __init__(self, inner, schema, backend_label: str):
        self._inner = inner
        self._schema = schema
        self._backend_label = backend_label

    def invoke(self, messages):
        try:
            result = self._inner.invoke(messages)
        except Exception as exc:
            normalized = normalize_structured_exception(self._backend_label, exc)
            raise normalized from exc
        return ensure_structured_result(
            self._schema,
            result,
            backend_label=self._backend_label,
        )


class _FriendlyStructuredChat:
    """Wrap API-key chat models so structured-output failures are actionable."""

    def __init__(self, inner, backend_label: str):
        self._inner = inner
        self._backend_label = backend_label

    def with_structured_output(self, schema):
        return _FriendlyStructured(
            self._inner.with_structured_output(schema),
            schema,
            self._backend_label,
        )

    def invoke(self, messages):
        return self._inner.invoke(messages)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _with_friendly_structured_errors(chat, backend_label: str):
    original = chat.with_structured_output

    def with_structured_output(schema, *args, **kwargs):
        return _FriendlyStructured(
            original(schema, *args, **kwargs),
            schema,
            backend_label,
        )

    object.__setattr__(chat, "with_structured_output", with_structured_output)
    return chat


def get_llm(
    tier: str,
    *,
    temperature: float = 0,
    max_tokens: int = 2000,
    timeout: int | None = None,
    structured_retries: int | None = None,
):
    """依分層與『當前後端』回傳設定好的 chat model（含重試）。"""
    backend = settings.current_backend()
    if backend == "claude_cli":
        from app.llm_cli import CLAUDE_TIER_MODELS, ClaudeCLIChat

        choice = settings.cli_model("claude_cli")
        model = CLAUDE_TIER_MODELS[tier] if choice == "auto" else choice
        return ClaudeCLIChat(
            model,
            max_tokens=max_tokens,
            timeout=timeout or 300,
            structured_retries=structured_retries or 3,
        )
    if backend == "codex_cli":
        from app.llm_cli import CodexCLIChat
        choice = settings.cli_model("codex_cli")
        return CodexCLIChat(tier, max_tokens=max_tokens,
                            model=None if choice == "auto" else choice,
                            timeout=timeout or 300,
                            structured_retries=structured_retries or 3)
    if backend == "openai":
        # BYOK：OpenAI 相容端點（OpenAI / DeepSeek / Gemini / Ollama / vLLM…）。
        from langchain_openai import ChatOpenAI
        kwargs = dict(model=settings.byok_model() or "gpt-4o-mini",
                      temperature=temperature, max_tokens=max_tokens, max_retries=4)
        if timeout is not None:
            kwargs["timeout"] = timeout
        if settings.byok_base_url():
            kwargs["base_url"] = settings.byok_base_url()
        if settings.byok_api_key():
            kwargs["api_key"] = settings.byok_api_key()
        return _with_friendly_structured_errors(ChatOpenAI(**kwargs), "API key 後端")
    if backend == "ollama":
        # 本機模型：Ollama 預設；llama.cpp 可用自訂 OpenAI 相容端點。
        from langchain_openai import ChatOpenAI
        kwargs = dict(
            model=settings.local_model_model() or "qwen3:8b",
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=2,
            base_url=settings.local_model_base_url(),
            api_key=settings.local_model_api_key(),
        )
        if timeout is not None:
            kwargs["timeout"] = timeout
        return _with_friendly_structured_errors(ChatOpenAI(**kwargs), "本機模型")
    if backend == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = dict(
            model=get_model(tier),
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=4,
        )
        if timeout is not None:
            kwargs["timeout"] = timeout
        return _with_friendly_structured_errors(ChatAnthropic(**kwargs), "Anthropic API")
    raise ValueError(f"unknown LLM_BACKEND: {backend!r}")


def research_structured(schema, messages, tier: str = "standard"):
    """若當前後端有內建上網工具（目前為 claude_cli 的 WebSearch/WebFetch），用之做結構化
    研究並回傳驗證後的模型；後端不支援則回 None，由呼叫端自行降級（如 Tavily / 一般知識）。"""
    backend = settings.current_backend()
    if backend == "claude_cli":
        from app.llm_cli import CLAUDE_TIER_MODELS, run_claude_structured_research

        return run_claude_structured_research(schema, messages, CLAUDE_TIER_MODELS[tier])
    return None
