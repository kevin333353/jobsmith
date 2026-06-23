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
    """從模型輸出抽出 JSON：去除 ```json 圍欄，否則取第一個 { 到最後一個 }。"""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _schema_instruction(schema_model: Type[BaseModel]) -> str:
    schema = schema_model.model_json_schema()
    return (
        "請『只』輸出一個符合下列 JSON Schema 的 JSON 物件，"
        "不要任何說明文字、不要 markdown 圍欄：\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def _parse_into(schema_model: Type[BaseModel], raw: str) -> BaseModel:
    return schema_model.model_validate_json(_extract_json(raw))


# ---------------------------------------------------------------------------
# Claude Code CLI（claude -p）
# ---------------------------------------------------------------------------

CLAUDE_TIER_MODELS = {"cheap": "haiku", "standard": "sonnet", "deep": "opus"}


def _run_claude(prompt: str, model: str) -> str:
    """呼叫 `claude -p`（訂閱），回傳模型文字。移除 ANTHROPIC_API_KEY 以走訂閱登入。"""
    exe = os.environ.get("CLAUDE_CLI_PATH") or shutil.which("claude")
    if not exe:
        raise RuntimeError("找不到 claude CLI，請確認已安裝並在 PATH。")
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    proc = subprocess.run(
        [exe, "-p", prompt, "--output-format", "json", "--model", model],
        input="", capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI 失敗（rc={proc.returncode}）：{(proc.stderr or '')[:300]}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude CLI 回報錯誤：{envelope.get('result')}")
    return envelope.get("result", "")


class _CLIStructured:
    """通用結構化包裝：呼叫 runner、抽 JSON、驗證、失敗重試。"""

    def __init__(self, runner, model, schema):
        self._runner = runner
        self._model = model
        self._schema = schema

    def invoke(self, messages):
        system, human = _messages_to_prompt(messages)
        base = f"{system}\n\n{human}\n\n{_schema_instruction(self._schema)}"
        prompt = base
        last_err = None
        for _ in range(_MAX_TRIES):
            raw = self._runner(prompt, self._model)
            try:
                return _parse_into(self._schema, raw)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_err = exc
                prompt = base + "\n\n（上次輸出無法解析為合法 JSON，請重新只輸出合法 JSON 物件）"
        raise RuntimeError(f"CLI 結構化輸出解析失敗：{last_err}")


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

def _run_codex(prompt: str, schema_model: Type[BaseModel] | None = None) -> str:
    """呼叫 `codex exec`（訂閱）。有 schema 時用 --output-schema 強制結構，
    並以 --output-last-message 取最終訊息。"""
    exe = os.environ.get("CODEX_CLI_PATH") or shutil.which("codex")
    if not exe:
        raise RuntimeError("找不到 codex CLI，請確認已安裝並在 PATH。")
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / "last.txt"
        args = [exe, "exec", "--skip-git-repo-check", "-s", "read-only",
                "-o", str(out_file)]
        if schema_model is not None:
            schema_file = Path(td) / "schema.json"
            schema_file.write_text(
                json.dumps(schema_model.model_json_schema(), ensure_ascii=False),
                encoding="utf-8",
            )
            args += ["--output-schema", str(schema_file)]
        args.append(prompt)
        proc = subprocess.run(
            args, input="", capture_output=True, text=True, encoding="utf-8",
            env=env, timeout=_TIMEOUT,
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
        system, human = _messages_to_prompt(messages)
        base = f"{system}\n\n{human}\n\n{_schema_instruction(self._schema)}"
        prompt = base
        last_err = None
        for _ in range(_MAX_TRIES):
            raw = _run_codex(prompt, self._schema)
            try:
                return _parse_into(self._schema, raw)
            except (ValidationError, json.JSONDecodeError) as exc:
                last_err = exc
                prompt = base + "\n\n（上次輸出無法解析為合法 JSON，請重新只輸出合法 JSON 物件）"
        raise RuntimeError(f"CLI 結構化輸出解析失敗：{last_err}")


class CodexCLIChat:
    """相容 LangChain 介面的 Codex CLI 後端（使用 codex 設定的預設模型）。"""

    def __init__(self, tier: str = "standard", max_tokens: int = 2000):
        self.tier = tier
        self.max_tokens = max_tokens

    def with_structured_output(self, schema):
        return _CodexStructured(schema)

    def invoke(self, messages):
        system, human = _messages_to_prompt(messages)
        return _run_codex(f"{system}\n\n{human}", None)
