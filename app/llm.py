"""依 LLM_BACKEND 建立 LLM（介面一致：.with_structured_output(...).invoke(...)）。"""
import os

from app import settings
from app.settings import get_model


def get_llm(tier: str, *, temperature: float = 0, max_tokens: int = 2000):
    """依分層與後端回傳設定好的 chat model（含重試）。"""
    backend = settings.LLM_BACKEND
    if backend == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=get_model(tier),
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=4,
        )
    if backend == "qianfan":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url=settings.QIANFAN_BASE_URL,
            api_key=os.environ.get("QIANFAN_API_KEY", "missing"),
            model=settings.QIANFAN_MODEL_TIERS[tier],
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=4,
        )
    if backend == "claude_cli":
        from app.llm_cli import ClaudeCLIChat, CLAUDE_TIER_MODELS
        return ClaudeCLIChat(CLAUDE_TIER_MODELS[tier], max_tokens=max_tokens)
    if backend == "codex_cli":
        from app.llm_cli import CodexCLIChat
        return CodexCLIChat(tier, max_tokens=max_tokens)
    raise ValueError(f"unknown LLM_BACKEND: {backend!r}")
