"""逐節點 LLM 用量（token / 成本）蒐集。

設計（修正 M9 審查發現的兩個 bug）：
- 不靠「整條 run 共用一個蒐集器」——那個 contextvar 在 Starlette 把同步 SSE 產生器丟
  threadpool 時，會在每次 next() 進到新複製的 context 而遺失（只有第一個節點記得到）。
- 改成「每個節點自己開一個蒐集器」：graph._safe 在節點開始時 begin_node()（在該節點自身的
  context 設一個新 list），節點內的 LLM 呼叫 record_llm() 寫進去，結束時 end_node() 彙整並還原。
  因為平行生成節點各自跑在 copy_context() 的獨立 context，彼此的蒐集器天然隔離（不會互相灌數字）。
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


def begin_node():
    """節點開始：在本節點 context 開新蒐集器，回傳 token 供 end_node 還原。"""
    return _SINK.set([])


def end_node(token) -> dict:
    """節點結束：彙整本節點蒐集到的用量並還原 context（呼叫前的狀態）。"""
    sink = _SINK.get() or []
    usage = {
        "calls": len(sink),
        "input_tokens": sum(c.input_tokens for c in sink),
        "output_tokens": sum(c.output_tokens for c in sink),
        "cost_usd": round(sum(c.cost_usd for c in sink), 6),
    }
    try:
        _SINK.reset(token)
    except (ValueError, LookupError):  # token 屬於別的 context（理論上不會）：保險忽略
        pass
    return usage


def record_llm(input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0) -> None:
    """後端每次 LLM 呼叫後回報用量；不在節點蒐集區間內（sink=None）則略過。"""
    sink = _SINK.get()
    if sink is not None:
        sink.append(LLMCall(int(input_tokens or 0), int(output_tokens or 0), float(cost_usd or 0.0)))
