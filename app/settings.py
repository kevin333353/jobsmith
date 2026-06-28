"""集中管理環境變數、模型分層、與『可切換的 LLM 後端』。"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # 從 .env 載入 ANTHROPIC_API_KEY、LLM_BACKEND、OPENAI_* 等

# 模型分層：依任務難度選模型，集中於此便於切換與成本控制。
MODEL_TIERS: dict[str, str] = {
    "cheap": "claude-haiku-4-5-20251001",   # 單純抽取（解析）
    "standard": "claude-sonnet-4-6",        # 匹配/生成主力
    "deep": "claude-opus-4-8",              # Critic/Supervisor 硬判斷
}


def get_model(tier: str) -> str:
    """取得某分層對應的 model id；未知分層丟 KeyError。"""
    return MODEL_TIERS[tier]


# 可選後端（仿 open-design 的「本機 CLI ＋ BYOK」）：
# - claude_cli / codex_cli：本機 CLI 訂閱，免 API key、不吃額度（預設，主推）。
# - openai：BYOK 的 OpenAI 相容端點（base_url + key + model），一個後端吃 OpenAI / DeepSeek /
#           Gemini / Groq / OpenRouter / Ollama / LM Studio / vLLM 等任何相容服務。
# - anthropic：Anthropic API 金鑰（雲端/部署可選，不在主選單露出）。
SUPPORTED_BACKENDS: tuple[str, ...] = ("claude_cli", "codex_cli", "openai", "anthropic")

BACKEND_LABELS: dict[str, str] = {
    "claude_cli": "Claude Code CLI（訂閱）",
    "codex_cli": "Codex CLI（訂閱）",
    "openai": "OpenAI 相容 (BYOK)",
    "anthropic": "Anthropic API（金鑰）",
}

# 後端類型：cli=本機 CLI 訂閱、byok=自帶金鑰的 OpenAI 相容端點、api=雲端 API 金鑰。
BACKEND_KIND: dict[str, str] = {
    "claude_cli": "cli", "codex_cli": "cli", "openai": "byok", "anthropic": "api",
}

# 啟動時的後端（.env 的 LLM_BACKEND；預設本機 claude_cli）。執行期可由 set_backend 切換。
_current_backend: str = os.environ.get("LLM_BACKEND", "claude_cli")


def current_backend() -> str:
    """目前作用中的 LLM 後端。"""
    return _current_backend


def set_backend(name: str, *, persist: bool = False) -> None:
    """切換 LLM 後端（供 UI 設定用）；只接受 SUPPORTED_BACKENDS。"""
    global _current_backend
    if name not in SUPPORTED_BACKENDS:
        raise ValueError(f"unsupported backend: {name!r}（可選：{', '.join(SUPPORTED_BACKENDS)}）")
    _current_backend = name
    if persist:
        _write_env({"LLM_BACKEND": _current_backend})


# ---------------------------------------------------------------------------
# 本機 CLI 模型策略：'auto' = 使用 Jobsmith 內建安全預設（Codex 不指定模型，Claude 依任務分層）。
# 不在 UI 硬編碼模型名，避免使用者誤以為下拉選項是實際偵測到、可呼叫的模型。
# ---------------------------------------------------------------------------
CLI_MODEL_CHOICES: dict[str, list[str]] = {
    "claude_cli": ["auto"],
    "codex_cli": ["auto"],
}
_cli_model: dict[str, str] = {"claude_cli": "auto", "codex_cli": "auto"}


def cli_model(backend: str) -> str:
    """該 CLI 後端目前選的模型（'auto' = 自動分層）。"""
    return _cli_model.get(backend, "auto")


def set_cli_model(backend: str, model: str) -> None:
    """設定 CLI 後端的模型策略；非 CLI 後端或未知策略丟 ValueError。"""
    if backend not in _cli_model:
        raise ValueError(f"非 CLI 後端不支援模型選擇：{backend!r}")
    value = (model or "auto").strip() or "auto"
    if value not in CLI_MODEL_CHOICES[backend]:
        raise ValueError("本機 CLI 模型不可由 Jobsmith 硬編碼選擇；請使用 auto 或在 CLI 自身設定模型。")
    _cli_model[backend] = value


# ---------------------------------------------------------------------------
# BYOK（OpenAI 相容）：初值取自 .env，可由 UI 覆寫並寫回 .env（金鑰只存本機）。
# ---------------------------------------------------------------------------
_ENV_DEFAULT = Path(__file__).resolve().parent.parent / ".env"
_byok: dict[str, str] = {
    "base_url": os.environ.get("OPENAI_BASE_URL", "").strip(),
    "api_key": os.environ.get("OPENAI_API_KEY", "").strip(),
    "model": os.environ.get("OPENAI_MODEL", "").strip(),
}
_ENV_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _env_file() -> Path:
    """.env 路徑（測試可用 COPILOT_ENV_FILE 改指向暫存檔，避免動到真檔）。"""
    return Path(os.environ.get("COPILOT_ENV_FILE") or _ENV_DEFAULT)


def byok_base_url() -> str:
    return _byok["base_url"]


def byok_api_key() -> str:
    return _byok["api_key"]


def byok_model() -> str:
    return _byok["model"]


def byok_public() -> dict:
    """供 UI：回設定狀態，但不外洩完整金鑰（只回是否已設定）。"""
    return {
        "base_url": _byok["base_url"],
        "model": _byok["model"],
        "has_key": bool(_byok["api_key"]),
    }


def _env_value(name: str, value: str) -> str:
    raw = value or ""
    if _ENV_CONTROL_CHARS.search(raw):
        raise ValueError(f"{name} must not contain control characters")
    return raw.strip()


def set_byok(
    base_url: str = "",
    api_key: str = "",
    model: str = "",
    *,
    persist: bool = True,
) -> None:
    """更新 BYOK 設定。api_key 為空 = 保留既有金鑰（UI 不會回傳真實金鑰，避免被清空）。"""
    clean_base_url = _env_value("OPENAI_BASE_URL", base_url)
    clean_model = _env_value("OPENAI_MODEL", model)
    clean_api_key = _env_value("OPENAI_API_KEY", api_key)
    _byok["base_url"] = clean_base_url
    _byok["model"] = clean_model
    if clean_api_key:
        _byok["api_key"] = clean_api_key
    if persist:
        _write_env({
            "OPENAI_BASE_URL": _byok["base_url"],
            "OPENAI_MODEL": _byok["model"],
            "OPENAI_API_KEY": _byok["api_key"],
        })


def _write_env(updates: dict[str, str]) -> None:
    """把 key=value upsert 進 .env（保留其他行、不加引號）；值為空則移除該行。寫檔失敗不致命。"""
    safe_updates = {key: _env_value(key, val) for key, val in updates.items()}
    path = _env_file()
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    except Exception:
        lines = []
    remaining = dict(safe_updates)
    out: list[str] = []
    for line in lines:
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        key = m.group(1) if m else None
        if key in remaining:
            val = remaining.pop(key)
            if val:
                out.append(f"{key}={val}")
            # 值為空 → 略過（等同移除該行）
        else:
            out.append(line)
    for key, val in remaining.items():
        if val:
            out.append(f"{key}={val}")
    try:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    except Exception:
        pass  # 記憶體已更新，寫檔失敗不影響執行期
