import json

import pytest
from pydantic import BaseModel

import app.llm_cli as cli
from app.llm_errors import LLMResponseFormatError


class Toy(BaseModel):
    name: str
    score: int


def test_messages_to_prompt():
    s, h = cli._messages_to_prompt([("system", "S1"), ("human", "H1"), ("system", "S2")])
    assert "S1" in s and "S2" in s
    assert h == "H1"


def test_extract_json_plain():
    assert json.loads(cli._extract_json('{"a": 1}'))["a"] == 1


def test_extract_json_fenced():
    raw = "前言\n```json\n{\"a\": 2}\n```\n後語"
    assert json.loads(cli._extract_json(raw))["a"] == 2


def test_extract_json_embedded():
    raw = "這是結果：{\"a\": 3} 謝謝"
    assert json.loads(cli._extract_json(raw))["a"] == 3


def test_extract_json_nested_object():
    # 巢狀物件：舊的「第一個 { 到最後一個 }」在有後綴雜訊時會壞，平衡掃描要正確
    raw = '前言 {"outer": {"inner": [1, 2]}, "name": "王"} 後綴'
    obj = json.loads(cli._extract_json(raw))
    assert obj["outer"]["inner"] == [1, 2] and obj["name"] == "王"


def test_extract_json_stops_at_first_complete_object():
    raw = '{"a": 1} 然後又冒出一段 {"b": 2}'
    assert json.loads(cli._extract_json(raw)) == {"a": 1}


def test_extract_json_brace_inside_string():
    raw = '{"note": "包含 } 與 { 大括號", "score": 7}'
    assert json.loads(cli._extract_json(raw))["score"] == 7


def test_claude_structured_repairs_validation_error(monkeypatch):
    # 驗證失敗時，重試提示要帶欄位級錯誤（提到缺少的 score），而非通用嘮叨
    prompts = []
    calls = {"n": 0}

    def runner(prompt, model, timeout=None):
        prompts.append(prompt)
        calls["n"] += 1
        return '{"name": "x"}' if calls["n"] == 1 else '{"name": "x", "score": 9}'

    monkeypatch.setattr(cli, "_run_claude", runner)
    out = cli.ClaudeCLIChat("haiku").with_structured_output(Toy).invoke([("human", "h")])
    assert out.score == 9 and calls["n"] == 2
    assert "score" in prompts[1]


def test_claude_structured_parses(monkeypatch):
    monkeypatch.setattr(cli, "_run_claude", lambda prompt, model, timeout=None: '{"name": "王", "score": 88}')
    llm = cli.ClaudeCLIChat("opus")
    out = llm.with_structured_output(Toy).invoke([("system", "s"), ("human", "h")])
    assert isinstance(out, Toy)
    assert out.name == "王" and out.score == 88


def test_claude_structured_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def runner(prompt, model, timeout=None):
        calls["n"] += 1
        return "亂碼非 JSON" if calls["n"] == 1 else '{"name": "x", "score": 1}'

    monkeypatch.setattr(cli, "_run_claude", runner)
    out = cli.ClaudeCLIChat("haiku").with_structured_output(Toy).invoke([("human", "h")])
    assert out.score == 1
    assert calls["n"] == 2


def test_structured_loop_can_limit_retries():
    calls = {"n": 0}

    def runner(prompt):
        calls["n"] += 1
        return "not json"

    with pytest.raises(LLMResponseFormatError):
        cli._structured_loop(runner, Toy, [("human", "h")], "CLI", max_tries=1)

    assert calls["n"] == 1


def test_structured_loop_reports_empty_cli_response(monkeypatch):
    monkeypatch.setattr(cli, "_run_claude", lambda prompt, model, timeout=None: "   ")
    with pytest.raises(LLMResponseFormatError) as ei:
        cli.ClaudeCLIChat("haiku").with_structured_output(Toy).invoke([("human", "h")])
    assert "回覆空白" in str(ei.value)


def test_structured_loop_reports_non_json_cli_response(monkeypatch):
    monkeypatch.setattr(cli, "_run_codex", lambda prompt, timeout=None, extra_args=None: "not json")
    with pytest.raises(LLMResponseFormatError) as ei:
        cli.CodexCLIChat().with_structured_output(Toy).invoke([("human", "h")])
    assert "不是合法 JSON" in str(ei.value)


def test_run_claude_strips_api_key_and_parses(monkeypatch):
    seen = {}

    class FakeProc:
        returncode = 0
        stdout = json.dumps({"is_error": False, "result": "答案"})
        stderr = ""

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["env"] = kwargs.get("env", {})
        seen["timeout"] = kwargs.get("timeout")
        return FakeProc()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-be-removed")
    monkeypatch.setattr(cli, "_run_process", fake_run)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "claude")
    out = cli._run_claude("hi", "haiku")
    assert out == "答案"
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert "--model" in seen["args"]


def test_run_claude_raises_on_error_envelope(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = json.dumps({"is_error": True, "result": "Invalid API key"})
        stderr = ""

    monkeypatch.setattr(cli, "_run_process", lambda args, **kw: FakeProc())
    monkeypatch.setattr(cli.shutil, "which", lambda name: "claude")
    with pytest.raises(RuntimeError):
        cli._run_claude("hi", "haiku")


def test_codex_structured_parses(monkeypatch):
    monkeypatch.setattr(
        cli, "_run_codex", lambda prompt, timeout=None, extra_args=None: '{"name": "c", "score": 5}'
    )
    out = cli.CodexCLIChat().with_structured_output(Toy).invoke([("human", "h")])
    assert out.name == "c" and out.score == 5


def test_codex_structured_prompt_does_not_start_with_blank(monkeypatch):
    seen = {}

    def runner(prompt, timeout=None, extra_args=None):
        seen["prompt"] = prompt
        return '{"name": "c", "score": 5}'

    monkeypatch.setattr(cli, "_run_codex", runner)
    cli.CodexCLIChat().with_structured_output(Toy).invoke([("human", "h")])

    assert not seen["prompt"].startswith("\n")


def test_codex_invoke_prompt_does_not_start_with_blank(monkeypatch):
    seen = {}

    def runner(prompt, timeout=None, extra_args=None):
        seen["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(cli, "_run_codex", runner)
    cli.CodexCLIChat().invoke([("human", "h")])

    assert not seen["prompt"].startswith("\n")


def test_codex_invoke_uses_low_reasoning_effort(monkeypatch):
    seen = {}

    def runner(prompt, timeout=None, extra_args=None):
        seen["extra_args"] = extra_args
        return "ok"

    monkeypatch.setattr(cli, "_run_codex", runner)
    cli.CodexCLIChat().invoke([("human", "h")])

    assert seen["extra_args"] is not None
    assert 'model_reasoning_effort="low"' in seen["extra_args"]


def test_run_claude_strips_null_bytes_from_prompt(monkeypatch):
    # 履歷/JD 偶有殘留 \x00（UTF-16 .txt、某些 PDF）；
    # 直接進 subprocess 會丟 ValueError("embedded null byte")。
    # 這正是「一按搜尋就 AI 服務暫時無法使用（ValueError）」的根因。送進 args 的 prompt 必須先清掉。
    seen = {}

    class FakeProc:
        returncode = 0
        stdout = json.dumps({"is_error": False, "result": "ok"})
        stderr = ""

    def fake_run(args, **kwargs):
        seen["args"] = args
        return FakeProc()

    monkeypatch.setattr(cli, "_run_process", fake_run)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "claude")
    cli._run_claude("履歷\x00內容\x00殘留", "haiku")
    assert all("\x00" not in a for a in seen["args"])


def test_run_claude_tolerates_noise_around_json_envelope(monkeypatch):
    # claude CLI 偶爾在 --output-format json 的 JSON 前後夾橫幅/更新提示，直接 json.loads 會炸；
    # 用 _extract_json 把 envelope 抽出來才穩。
    class FakeProc:
        returncode = 0
        stdout = (
            "⚠ update available\n"
            + json.dumps({"is_error": False, "result": "答案"})
            + "\nbye"
        )
        stderr = ""

    monkeypatch.setattr(cli, "_run_process", lambda args, **kw: FakeProc())
    monkeypatch.setattr(cli.shutil, "which", lambda name: "claude")
    assert cli._run_claude("hi", "haiku") == "答案"


def test_run_claude_raises_clear_error_on_non_json(monkeypatch):
    # stdout 完全不是 JSON（如要求重新登入）時，要丟帶『實際 stdout』的 RuntimeError，
    # 而非無解的 JSONDecodeError——這正是同事 claude 端「JSON decode error」看不出原因的痛點。
    class FakeProc:
        returncode = 0
        stdout = "Please run `claude login` first."
        stderr = ""

    monkeypatch.setattr(cli, "_run_process", lambda args, **kw: FakeProc())
    monkeypatch.setattr(cli.shutil, "which", lambda name: "claude")
    with pytest.raises(RuntimeError) as ei:
        cli._run_claude("hi", "haiku")
    assert "claude login" in str(ei.value)


def test_run_codex_strips_null_bytes_from_prompt(monkeypatch):
    seen = {}

    class FakeProc:
        returncode = 0
        stdout = "{}"
        stderr = ""

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["stdin_text"] = kwargs.get("stdin_text")
        return FakeProc()

    monkeypatch.setattr(cli, "_run_process", fake_run)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "codex")
    cli._run_codex("JD\x00內容\x00殘留")
    assert all("\x00" not in a for a in seen["args"])
    assert "\x00" not in seen["stdin_text"]


def test_run_codex_strips_leading_blank_prompt(monkeypatch):
    seen = {}

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["prompt"] = kwargs.get("stdin_text")
        out_file = args[args.index("-o") + 1]
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("ok")
        return FakeProc()

    monkeypatch.setattr(cli, "_run_process", fake_run)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "codex")
    cli._run_codex("\n\nReply with exactly: OK")

    assert seen["args"][-1] == "-"
    assert seen["prompt"] == "Reply with exactly: OK"


def test_run_codex_sends_prompt_via_stdin(monkeypatch):
    seen = {}

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["stdin_text"] = kwargs.get("stdin_text")
        out_file = args[args.index("-o") + 1]
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("ok")
        return FakeProc()

    monkeypatch.setattr(cli, "_run_process", fake_run)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "codex")
    cli._run_codex("long prompt")

    assert seen["args"][-1] == "-"
    assert "long prompt" not in seen["args"]
    assert seen["stdin_text"] == "long prompt"


def test_run_codex_adds_cli_directory_to_child_path(tmp_path, monkeypatch):
    # macOS GUI app 不會載入 shell profile；若 codex 是 nvm/npm shim
    # (#!/usr/bin/env node)，子程序 PATH 需要包含 shim 所在的 node bin 才找得到 node。
    seen = {}

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    bin_dir = tmp_path / ".nvm" / "versions" / "node" / "v22.22.1" / "bin"
    exe = bin_dir / "codex"
    exe.parent.mkdir(parents=True)
    exe.write_text("")

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["env"] = kwargs.get("env", {})
        out_file = args[args.index("-o") + 1]
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("ok")
        return FakeProc()

    monkeypatch.setenv("PATH", "/usr/bin" + cli.os.pathsep + "/bin")
    monkeypatch.setattr(cli, "_find_cli", lambda name, env_var: str(exe))
    monkeypatch.setattr(cli, "_run_process", fake_run)

    cli._run_codex("hello")

    child_path = seen["env"]["PATH"].split(cli.os.pathsep)
    assert child_path[0] == str(bin_dir)
    assert str(bin_dir) in child_path


def test_find_cli_prefers_env_override(monkeypatch):
    monkeypatch.setenv("CLAUDE_CLI_PATH", "/custom/claude")
    monkeypatch.setattr(cli.shutil, "which", lambda n: "/on/path/claude")
    assert cli._find_cli("claude", "CLAUDE_CLI_PATH") == "/custom/claude"


def test_find_cli_uses_which_when_no_override(monkeypatch):
    monkeypatch.delenv("CLAUDE_CLI_PATH", raising=False)
    monkeypatch.setattr(cli.shutil, "which", lambda n: "/on/path/claude")
    assert cli._find_cli("claude", "CLAUDE_CLI_PATH") == "/on/path/claude"


def test_find_cli_falls_back_to_common_install_paths(tmp_path, monkeypatch):
    # 模擬 GUI/exe：PATH 找不到（which→None），但執行檔在常見安裝路徑（npm/.local…）。
    # 這正是「終端機跑得動、雙擊 app 卻每個 AI 呼叫都靜默降級」的根因。
    monkeypatch.delenv("CODEX_CLI_PATH", raising=False)
    monkeypatch.setattr(cli.shutil, "which", lambda n: None)
    fake = tmp_path / "codex.cmd"
    fake.write_text("")
    monkeypatch.setattr(cli, "_cli_search_paths", lambda name: [tmp_path / "nope", fake])
    assert cli._find_cli("codex", "CODEX_CLI_PATH") == str(fake)


def test_find_cli_falls_back_to_nvm_install_paths(tmp_path, monkeypatch):
    # macOS GUI app 不會載入 shell profile；nvm 裝的 npm global CLI 會藏在 ~/.nvm/versions/node/*/bin。
    # 這個 home-relative 掃描在 Windows 測試環境也安全，能避免把 pathlib 強行切成 PosixPath。
    monkeypatch.delenv("CLAUDE_CLI_PATH", raising=False)
    monkeypatch.setattr(cli.shutil, "which", lambda n: None)
    monkeypatch.setattr(cli.Path, "home", lambda: tmp_path)
    fake = tmp_path / ".nvm" / "versions" / "node" / "v22.22.1" / "bin" / "claude"
    fake.parent.mkdir(parents=True)
    fake.write_text("")

    assert cli._find_cli("claude", "CLAUDE_CLI_PATH") == str(fake)


def test_find_cli_returns_none_when_missing_everywhere(monkeypatch):
    monkeypatch.delenv("CLAUDE_CLI_PATH", raising=False)
    monkeypatch.setattr(cli.shutil, "which", lambda n: None)
    monkeypatch.setattr(cli, "_cli_search_paths", lambda name: [])
    assert cli._find_cli("claude", "CLAUDE_CLI_PATH") is None
