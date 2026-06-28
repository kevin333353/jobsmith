import importlib
from pathlib import Path

import pytest

import app.llm as llm_mod
import app.settings as settings_mod
from app.llm_errors import LLMResponseFormatError
from tests.test_llm_cli import Toy


def _reload(monkeypatch, backend):
    monkeypatch.setenv("LLM_BACKEND", backend)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    importlib.reload(settings_mod)
    importlib.reload(llm_mod)
    return llm_mod


def test_anthropic_backend_selected(monkeypatch):
    m = _reload(monkeypatch, "anthropic")
    llm = m.get_llm("standard")
    assert llm.model == "claude-sonnet-4-6"


def test_unknown_backend_raises(monkeypatch):
    m = _reload(monkeypatch, "nonsense")
    import pytest
    with pytest.raises(ValueError):
        m.get_llm("standard")


def test_set_backend_switches_at_runtime(monkeypatch):
    _reload(monkeypatch, "claude_cli")
    assert settings_mod.current_backend() == "claude_cli"
    settings_mod.set_backend("codex_cli")
    assert settings_mod.current_backend() == "codex_cli"
    from app.llm_cli import CodexCLIChat
    assert isinstance(llm_mod.get_llm("standard"), CodexCLIChat)


def test_set_backend_rejects_unsupported(monkeypatch):
    import pytest
    _reload(monkeypatch, "claude_cli")
    with pytest.raises(ValueError):
        settings_mod.set_backend("qianfan")


def test_claude_cli_backend_selected(monkeypatch):
    m = _reload(monkeypatch, "claude_cli")
    from app.llm_cli import ClaudeCLIChat
    llm = m.get_llm("deep")
    assert isinstance(llm, ClaudeCLIChat)
    assert llm.model == "opus"


def test_codex_cli_backend_selected(monkeypatch):
    m = _reload(monkeypatch, "codex_cli")
    from app.llm_cli import CodexCLIChat
    llm = m.get_llm("standard")
    assert isinstance(llm, CodexCLIChat)


def test_openai_backend_selected(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "deepseek-chat")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    importlib.reload(settings_mod)
    importlib.reload(llm_mod)
    from langchain_openai import ChatOpenAI
    llm = llm_mod.get_llm("standard")
    assert isinstance(llm, ChatOpenAI)
    assert getattr(llm, "model_name", getattr(llm, "model", None)) == "deepseek-chat"


def test_claude_cli_rejects_manual_model_override(monkeypatch):
    m = _reload(monkeypatch, "claude_cli")
    settings_mod.set_cli_model("claude_cli", "auto")
    assert m.get_llm("deep").model == "opus"         # auto 使用 Jobsmith 分層預設
    with pytest.raises(ValueError):
        settings_mod.set_cli_model("claude_cli", "sonnet")


def test_codex_cli_rejects_manual_model_override(monkeypatch):
    m = _reload(monkeypatch, "codex_cli")
    settings_mod.set_cli_model("codex_cli", "auto")
    llm = m.get_llm("standard")
    assert llm.model is None
    assert llm._extra() == [
        "-c",
        'model_reasoning_effort="low"',
    ]
    with pytest.raises(ValueError):
        settings_mod.set_cli_model("codex_cli", "gpt-5-codex")


def test_set_cli_model_rejects_non_cli(monkeypatch):
    import pytest
    _reload(monkeypatch, "claude_cli")
    with pytest.raises(ValueError):
        settings_mod.set_cli_model("anthropic", "x")


def test_set_byok_persists_to_env(monkeypatch):
    # 用 CWD 本地暫存檔（本機 AppData\Temp 受限，tmp_path fixture 在此會 PermissionError）
    env = Path("_byok_settings_test.env")
    env.unlink(missing_ok=True)
    monkeypatch.setenv("COPILOT_ENV_FILE", str(env))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    importlib.reload(settings_mod)
    try:
        settings_mod.set_byok("https://api.x.com/v1", "sk-secret", "gpt-4o-mini")
        txt = env.read_text(encoding="utf-8")
        assert "OPENAI_BASE_URL=https://api.x.com/v1" in txt
        assert "OPENAI_API_KEY=sk-secret" in txt
        assert "OPENAI_MODEL=gpt-4o-mini" in txt
        pub = settings_mod.byok_public()
        assert pub["has_key"] is True and "api_key" not in pub   # 不外洩金鑰
        # 空 api_key 不清掉既有金鑰
        settings_mod.set_byok("https://api.x.com/v1", "", "gpt-4o")
        assert settings_mod.byok_api_key() == "sk-secret"
        assert settings_mod.byok_model() == "gpt-4o"
    finally:
        env.unlink(missing_ok=True)


def test_set_byok_rejects_env_newline_in_values(monkeypatch):
    import pytest

    env = Path("_byok_settings_injection_test.env")
    env.unlink(missing_ok=True)
    monkeypatch.setenv("COPILOT_ENV_FILE", str(env))
    importlib.reload(settings_mod)
    try:
        with pytest.raises(ValueError):
            settings_mod.set_byok(
                "https://api.example/v1\nOPENAI_API_KEY=leaked",
                "sk-secret",
                "gpt-4o",
            )
        if env.exists():
            assert "OPENAI_API_KEY=leaked" not in env.read_text(encoding="utf-8")
    finally:
        env.unlink(missing_ok=True)


def test_research_structured_none_for_non_cli(monkeypatch):
    # 非 claude_cli 後端沒有內建上網工具 → research_structured 回 None（呼叫端自行降級）
    m = _reload(monkeypatch, "anthropic")
    assert m.research_structured(object, [("human", "x")]) is None


def test_research_structured_uses_claude_cli(monkeypatch):
    # claude_cli 後端 → 走 run_claude_structured_research（此處 mock 掉，不打真的 CLI）
    m = _reload(monkeypatch, "claude_cli")
    import app.llm_cli as cli
    calls = {}

    def fake(schema, messages, model):
        calls["model"] = model
        return "SENTINEL"
    monkeypatch.setattr(cli, "run_claude_structured_research", fake)
    out = m.research_structured(object, [("human", "x")], tier="standard")
    assert out == "SENTINEL"
    assert calls["model"] == "sonnet"


def test_api_structured_wrapper_reports_empty_response():
    class EmptyStructured:
        def invoke(self, messages):
            return None

    class FakeChat:
        def with_structured_output(self, schema):
            return EmptyStructured()

    wrapped = llm_mod._FriendlyStructuredChat(FakeChat(), "openai")
    with pytest.raises(LLMResponseFormatError) as ei:
        wrapped.with_structured_output(Toy).invoke([("human", "h")])
    assert "回覆空白" in str(ei.value)
