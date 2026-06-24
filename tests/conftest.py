import os
import json
from pathlib import Path

# 測試用 in-memory checkpointer（須在 import app.server 建 GRAPH 前設定），避免汙染真實 db。
os.environ.setdefault("COPILOT_DB", ":memory:")

import pytest

from app.models import Profile, ParsedJob


class _FakeStructured:
    def __init__(self, result):
        self._result = result

    def invoke(self, messages):
        return self._result


class FakeLLM:
    """模擬 ChatAnthropic：with_structured_output(...).invoke(...) 回傳預設結果。"""
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        return _FakeStructured(self._result)


@pytest.fixture
def demo_profile() -> Profile:
    data = json.loads(Path("data/demo_profile.json").read_text(encoding="utf-8"))
    return Profile(**data)


@pytest.fixture
def sample_parsed_job() -> ParsedJob:
    return ParsedJob(
        title="AI 工程師",
        company="未來智能股份有限公司",
        location="台北",
        responsibilities=["開發 LLM 應用", "設計 multi-agent 流程"],
        required_skills=["Python", "LangChain", "LLM"],
        nice_to_have=["RAG", "FastAPI"],
        min_years=2,
        tech_stack=["Python", "LangChain"],
        language="zh",
        salary=None,
    )
