"""ChatAnthropic 的薄包裝：依分層建立 LLM。"""
from langchain_anthropic import ChatAnthropic

from app.settings import get_model


def get_llm(tier: str, *, temperature: float = 0, max_tokens: int = 2000) -> ChatAnthropic:
    """依模型分層回傳設定好的 ChatAnthropic 實例。"""
    return ChatAnthropic(
        model=get_model(tier),
        temperature=temperature,
        max_tokens=max_tokens,
    )
