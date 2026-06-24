"""逐次 LLM 呼叫的 token / 成本蒐集（供 agent telemetry 用）。

單人本機假設：用 contextvar 隔離每次 run 的蒐集器（同一執行緒內的 graph 節點共用）。
後端（claude_cli）在每次 LLM 呼叫時 record_llm(...)；graph 的 _safe 以 marker()/drain_since()
取出單一節點期間累積的 token/成本，連同延遲寫進 state 的 telemetry 通道。
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass

_SINK: contextvars.ContextVar[list | None] = contextvars.ContextVar("llm_sink", default=None)


@dataclass
class LLMCall:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def start_run() -> None:
    """在一次 run 開始時呼叫（重置蒐集器）。"""
    _SINK.set([])


def record_llm(input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0) -> None:
    """後端每次 LLM 呼叫後回報用量（沒有作用中的 run 則略過）。"""
    sink = _SINK.get()
    if sink is not None:
        sink.append(LLMCall(int(input_tokens or 0), int(output_tokens or 0), float(cost_usd or 0.0)))


def marker() -> int:
    """回傳目前蒐集器長度，供節點起算。"""
    sink = _SINK.get()
    return len(sink) if sink is not None else 0


def drain_since(mark: int) -> dict:
    """彙總自 mark 起新增的 LLM 呼叫用量。"""
    sink = _SINK.get()
    if sink is None:
        return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    items = sink[mark:]
    return {
        "calls": len(items),
        "input_tokens": sum(c.input_tokens for c in items),
        "output_tokens": sum(c.output_tokens for c in items),
        "cost_usd": round(sum(c.cost_usd for c in items), 6),
    }
