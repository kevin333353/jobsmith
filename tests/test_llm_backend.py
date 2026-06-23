import importlib

import app.settings as settings_mod
import app.llm as llm_mod


def _reload(monkeypatch, backend):
    monkeypatch.setenv("LLM_BACKEND", backend)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("QIANFAN_API_KEY", "bce-v3/test")
    importlib.reload(settings_mod)
    importlib.reload(llm_mod)
    return llm_mod


def test_anthropic_backend_selected(monkeypatch):
    m = _reload(monkeypatch, "anthropic")
    llm = m.get_llm("standard")
    assert llm.model == "claude-sonnet-4-6"


def test_qianfan_backend_selected(monkeypatch):
    m = _reload(monkeypatch, "qianfan")
    llm = m.get_llm("standard")
    assert getattr(llm, "model_name", getattr(llm, "model", "")) == "deepseek-v3.2"


def test_qianfan_tier_map(monkeypatch):
    m = _reload(monkeypatch, "qianfan")
    assert m.get_llm("cheap").model_name == "minimax-m2.5"
    assert m.get_llm("deep").model_name == "deepseek-v4-pro"


def test_unknown_backend_raises(monkeypatch):
    m = _reload(monkeypatch, "nonsense")
    import pytest
    with pytest.raises(ValueError):
        m.get_llm("standard")


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
