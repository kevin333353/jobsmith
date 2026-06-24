"""以本機 CLI 訂閱當 LLM 後端：Claude Code（claude -p）與 Codex（codex exec）。

免 API key、不吃 API 額度，改用使用者的 CLI 訂閱。介面與其他後端一致：
`get_llm(...).with_structured_output(Model).invoke(messages)`。

結構化輸出策略：CLI 回傳文字而非原生 function-calling，故以「JSON Schema 提示 →
抽取 → Pydantic 驗證 → 失敗重試」實作（Codex 另用 --output-schema 由 CLI 強制 schema）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Type

from pydantic import BaseModel, ValidationError

_MAX_TRIES = 3
_TIMEOUT = 300


def _messages_to_prompt(messages) -> tuple[str, str]:
    """把 [(role, content), ...] 拆成 (system, human) 兩段合併字串。"""
    system_parts, human_parts = [], []
    for role, content in messages:
        if role == "system":
            system_parts.append(content)
        else:
            human_parts.append(content)
    return "\n\n".join(system_parts), "\n\n".join(human_parts)


def _extract_json(text: str) -> str:
    """抽出第一個完整 JSON 物件：去 markdown 圍欄後用平衡括號掃描（巢狀安全、忽略字串內括號）。"""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]  # 未閉合 → 交給驗證報錯


def _schema_instruction(schema_model: Type[BaseModel]) -> str:
    schema = schema_model.model_json_schema()
    return (
        "請『只』輸出一個符合下列 JSON Schema 的 JSON 物件，"
        "不要任何說明文字、不要 markdown 圍欄：\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def _parse_into(schema_model: Type[BaseModel], raw: str) -> BaseModel:
    return schema_model.model_validate_json(_extract_json(raw))


def _repair_hint(exc: ValidationError) -> str:
    """把 Pydantic 欄位級錯誤回灌提示，引導模型針對性修正（而非通用嘮叨）。"""
    problems = []
    for e in exc.errors()[:8]:
        loc = ".".join(str(p) for p in e.get("loc", ())) or "(root)"
        problems.append(f"- 欄位 `{loc}`：{e.get('msg')}")
    return ("上次輸出不符合 schema，請修正下列欄位後，重新只輸出一個合法 JSON 物件："
            "\n" + "\n".join(problems))


def _structured_loop(run_prompt, schema, messages):
    """共用結構化輸出迴圈：組提示 → 跑 → 抽/驗 → 失敗帶欄位錯誤重試。"""
    system, human = _messages_to_prompt(messages)
    base = f"{system}\n\n{human}\n\n{_schema_instruction(schema)}"
    prompt = base
    last_err = None
    for _ in range(_MAX_TRIES):
        raw = run_prompt(prompt)
        try:
            return _parse_into(schema, raw)
        except ValidationError as exc:
            last_err = exc
            prompt = base + "\n\n" + _repair_hint(exc)
        except json.JSONDecodeError as exc:
            last_err = exc
            prompt = base + "\n\n（上次輸出不是合法 JSON，請只輸出一個合法 JSON 物件，不要任何其他文字）"
    raise RuntimeError(f"CLI 結構化輸出解析失敗：{last_err}") from last_err


# ---------------------------------------------------------------------------
# Claude Code CLI（claude -p）
# ---------------------------------------------------------------------------

CLAUDE_TIER_MODELS = {"cheap": "haiku", "standard": "sonnet", "deep": "opus"}
# 讓模型可上網查證的內建工具（讀取型、headless 下免權限提示）
CLAUDE_RESEARCH_TOOLS = ["WebSearch", "WebFetch"]
_RESEARCH_TIMEOUT = 420  # 上網查證多輪，timeout 放寬


def _run_claude(prompt: str, model: str, allowed_tools: list[str] | None = None,
                timeout: int = _TIMEOUT) -> str:
    """呼叫 `claude -p`（訂閱），回傳模型文字。移除 ANTHROPIC_API_KEY 以走訂閱登入。

    allowed_tools 非空時帶 --allowedTools，讓模型可用 WebSearch/WebFetch 等工具上網查證。
    """
    exe = os.environ.get("CLAUDE_CLI_PATH") or shutil.which("claude")
    if not exe:
        raise RuntimeError("找不到 claude CLI，請確認已安裝並在 PATH。")
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    args = [exe, "-p", prompt, "--output-format", "json", "--model", model]
    if allowed_tools:
        args += ["--allowedTools", *allowed_tools]
    proc = subprocess.run(
        args, input="", capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI 失敗（rc={proc.returncode}）：{(proc.stderr or '')[:300]}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude CLI 回報錯誤：{envelope.get('result')}")
    _record_usage(envelope)
    return envelope.get("result", "")


def run_claude_structured_research(schema, messages, model: str):
    """用 WebSearch/WebFetch 上網查證 + 結構化輸出（claude_cli 專用，供公司情報 agent）。"""
    return _structured_loop(
        lambda prompt: _run_claude(prompt, model,
                                   allowed_tools=CLAUDE_RESEARCH_TOOLS, timeout=_RESEARCH_TIMEOUT),
        schema, messages,
    )


def _record_usage(envelope: dict) -> None:
    """把 claude -p envelope 的 usage / total_cost_usd 回報給 telemetry（先前直接丟棄）。"""
    try:
        from app import telemetry
        usage = envelope.get("usage") or {}
        in_tok = (int(usage.get("input_tokens", 0) or 0)
                  + int(usage.get("cache_read_input_tokens", 0) or 0)
                  + int(usage.get("cache_creation_input_tokens", 0) or 0))
        telemetry.record_llm(
            input_tokens=in_tok,
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            cost_usd=float(envelope.get("total_cost_usd", 0.0) or 0.0),
        )
    except Exception:  # telemetry 失敗不可影響主流程
        pass


class _CLIStructured:
    """通用結構化包裝：呼叫 runner、抽 JSON、驗證、失敗帶欄位錯誤重試。"""

    def __init__(self, runner, model, schema):
        self._runner = runner
        self._model = model
        self._schema = schema

    def invoke(self, messages):
        return _structured_loop(
            lambda prompt: self._runner(prompt, self._model), self._schema, messages)


class ClaudeCLIChat:
    """相容 LangChain 介面的 Claude Code CLI 後端。"""

    def __init__(self, model: str, max_tokens: int = 2000):
        self.model = model
        self.max_tokens = max_tokens  # CLI 不需要；保留以對齊介面

    def with_structured_output(self, schema):
        return _CLIStructured(_run_claude, self.model, schema)

    def invoke(self, messages):
        system, human = _messages_to_prompt(messages)
        return _run_claude(f"{system}\n\n{human}", self.model)


# ---------------------------------------------------------------------------
# Codex CLI（codex exec）
# ---------------------------------------------------------------------------

def _run_codex(prompt: str, timeout: int = _TIMEOUT, extra_args: list[str] | None = None) -> str:
    """呼叫 `codex exec`（訂閱），以 --output-last-message 取模型最終訊息。

    結構化輸出靠 prompt 內的 JSON Schema 指示 + 上層解析/重試（與 claude_cli 一致），
    不用 --output-schema：codex 的 --output-schema 走 OpenAI 嚴格 schema（需
    additionalProperties:false 等），Pydantic 預設 schema 不相容會直接報錯。
    """
    exe = os.environ.get("CODEX_CLI_PATH") or shutil.which("codex")
    if not exe:
        raise RuntimeError("找不到 codex CLI，請確認已安裝並在 PATH。")
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / "last.txt"
        # -o 為 --output-last-message 短旗標：把模型最終訊息寫入檔案，避免混入 agent log
        args = [exe, "exec", "--skip-git-repo-check", "-s", "read-only",
                "-o", str(out_file), *(extra_args or []), prompt]
        proc = subprocess.run(
            args, input="", capture_output=True, text=True, encoding="utf-8",
            env=env, timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"codex CLI 失敗（rc={proc.returncode}）：{(proc.stderr or '')[:300]}")
        if out_file.exists():
            return out_file.read_text(encoding="utf-8")
        return proc.stdout or ""


class _CodexStructured:
    def __init__(self, schema):
        self._schema = schema

    def invoke(self, messages):
        return _structured_loop(_run_codex, self._schema, messages)


class CodexCLIChat:
    """相容 LangChain 介面的 Codex CLI 後端（使用 codex 設定的預設模型）。"""

    def __init__(self, tier: str = "standard", max_tokens: int = 2000):
        self.tier = tier
        self.max_tokens = max_tokens

    def with_structured_output(self, schema):
        return _CodexStructured(schema)

    def invoke(self, messages):
        system, human = _messages_to_prompt(messages)
        return _run_codex(f"{system}\n\n{human}")
