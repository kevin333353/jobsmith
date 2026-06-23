# 台灣 AI 求職 Co-pilot — M1 實作計畫（Supervisor + 解析 + 匹配）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一個可在終端機執行的 LangGraph 圖：貼上 JD 文字 → 解析職缺 → 對使用者 Profile 打匹配分數 → 由 supervisor 依分數決定是否建議續做，並印出匹配報告。

**Architecture:** Supervisor / Orchestrator-Worker 的最小骨架。LangGraph `StateGraph` 串接兩個 agent 節點（① 解析、② 匹配）與一個條件分支（分數門檻決策）。每個 agent 用 `langchain_anthropic.ChatAnthropic` 搭配 `.with_structured_output(PydanticModel)` 取得強型別輸出；模型依「難度分層」由設定檔決定。

**Tech Stack:** Python 3.11+、LangGraph、langchain-anthropic、Pydantic v2、python-dotenv、pytest。（前端、FastAPI、其餘 agent 屬後續里程碑，本計畫不含。）

## Global Constraints

- **Python 版本**：3.11 以上。
- **語言**：產出與 prompt 以繁體中文為主。
- **資料策略**：不爬蟲、不自動投履歷；職缺資料一律由「貼 JD 文字」進入（URL 抓取屬後續里程碑）。
- **結構化輸出**：所有 agent 一律回傳 Pydantic v2 模型，不手刻 JSON 解析。
- **模型分層（model tiering）**，集中於 `app/settings.py`，可切換：
  - `cheap` = `claude-haiku-4-5-20251001`（解析等單純抽取）
  - `standard` = `claude-sonnet-4-6`（匹配/生成主力）
  - `deep` = `claude-opus-4-8`（Critic/Supervisor 硬判斷，本里程碑尚未用到）
  - 註：確切 model id／定價／rate limit 於執行時以 claude-api 參考核對；集中在 settings 便於修改。
- **金鑰**：`ANTHROPIC_API_KEY` 由環境變數/.env 提供，絕不寫進程式碼或 commit。
- **測試設計**：LLM 呼叫以注入假物件（monkeypatch `get_llm`）做**確定性**單元測試；真正打 API 的測試標記 `@pytest.mark.live`，預設略過。
- **流程**：TDD、DRY、YAGNI、頻繁 commit。

---

## File Structure（先鎖定分工）

```
app/
  __init__.py          # 套件標記
  settings.py          # 環境載入 + MODEL_TIERS 模型分層表
  llm.py               # get_llm(tier) -> ChatAnthropic 薄包裝
  models.py            # Pydantic: Profile / ParsedJob / MatchReport
  state.py             # LangGraph State（TypedDict）
  agents/
    __init__.py
    parse.py           # ① parse_job(jd_text) -> ParsedJob
    match.py           # ② match_profile(job, profile) -> MatchReport
  graph.py             # build_graph(): StateGraph 串接 + 條件分支
  cli.py               # 終端機進入點：讀 JD → 跑圖 → 印報告
data/
  demo_profile.json    # 範例求職者 Profile
  demo_jobs/
    ai_engineer.txt    # 範例 AI 職缺 JD（繁中）
tests/
  __init__.py
  conftest.py          # FakeLLM 假物件 + fixtures
  test_models.py
  test_parse.py
  test_match.py
  test_graph.py
  test_cli.py
requirements.txt
pyproject.toml         # 僅放 pytest 設定（pythonpath="."）
.env.example
README.md
```

每個檔案單一職責，files that change together live together（agents 同目錄）。

---

### Task 1: 專案骨架、設定與模型分層

**Files:**
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/settings.py`
- Create: `app/llm.py`
- Create: `README.md`
- Test: `tests/__init__.py`, `tests/test_settings.py`

**Interfaces:**
- Produces:
  - `app.settings.MODEL_TIERS: dict[str, str]`（鍵 `"cheap"`/`"standard"`/`"deep"`）
  - `app.settings.get_model(tier: str) -> str`
  - `app.llm.get_llm(tier: str, *, temperature: float = 0, max_tokens: int = 2000) -> ChatAnthropic`

- [ ] **Step 1: 建立依賴清單**

Create `requirements.txt`:

```
langgraph>=0.2
langchain-anthropic>=0.2
langchain-core>=0.3
pydantic>=2.7
python-dotenv>=1.0
pytest>=8.0
```

- [ ] **Step 2: 建立 pytest 設定**

Create `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
markers = [
    "live: 會真正呼叫 Anthropic API 的測試（預設略過，需 -m live 才跑）",
]
addopts = "-m 'not live'"
```

- [ ] **Step 3: 建立 .env 範本與套件標記**

Create `.env.example`:

```
ANTHROPIC_API_KEY=sk-ant-xxxxx
# 選用：開啟 LangSmith 追蹤
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=lsv2_xxxxx
# LANGSMITH_PROJECT=tw-job-copilot
```

Create `app/__init__.py`（空檔）與 `tests/__init__.py`（空檔）。

- [ ] **Step 4: 寫 settings 的失敗測試**

Create `tests/test_settings.py`:

```python
from app.settings import MODEL_TIERS, get_model


def test_model_tiers_have_three_levels():
    assert set(MODEL_TIERS) == {"cheap", "standard", "deep"}


def test_get_model_returns_configured_id():
    assert get_model("standard") == MODEL_TIERS["standard"]
    assert get_model("standard").startswith("claude-")


def test_get_model_rejects_unknown_tier():
    import pytest
    with pytest.raises(KeyError):
        get_model("nope")
```

- [ ] **Step 5: 執行測試確認失敗**

Run: `pytest tests/test_settings.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.settings'`）

- [ ] **Step 6: 實作 settings.py**

Create `app/settings.py`:

```python
"""集中管理環境變數與模型分層。"""
from dotenv import load_dotenv

load_dotenv()  # 從 .env 載入 ANTHROPIC_API_KEY 等

# 模型分層：依任務難度選模型，集中於此便於切換與成本控制。
MODEL_TIERS: dict[str, str] = {
    "cheap": "claude-haiku-4-5-20251001",   # 單純抽取（解析）
    "standard": "claude-sonnet-4-6",        # 匹配/生成主力
    "deep": "claude-opus-4-8",              # Critic/Supervisor 硬判斷
}


def get_model(tier: str) -> str:
    """取得某分層對應的 model id；未知分層丟 KeyError。"""
    return MODEL_TIERS[tier]
```

- [ ] **Step 7: 執行測試確認通過**

Run: `pytest tests/test_settings.py -v`
Expected: PASS（3 passed）

- [ ] **Step 8: 實作 llm.py（薄包裝）**

Create `app/llm.py`:

```python
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
```

- [ ] **Step 9: 建立 README 骨架**

Create `README.md`:

```markdown
# 台灣 AI 求職 Co-pilot

用一個 multi-agent 系統，幫你找 AI agent 的工作。M1：貼 JD → 解析 → 匹配評分。

## 設定
1. `python -m venv .venv && .venv\Scripts\activate`（Windows）
2. `pip install -r requirements.txt`
3. 複製 `.env.example` 為 `.env`，填入 `ANTHROPIC_API_KEY`

## 執行
`python -m app.cli data/demo_jobs/ai_engineer.txt`

## 測試
`pytest`（預設略過 live API 測試；跑真打 API 的測試：`pytest -m live`）
```

- [ ] **Step 10: Commit**

```bash
git add requirements.txt pyproject.toml .env.example app/__init__.py app/settings.py app/llm.py README.md tests/__init__.py tests/test_settings.py
git commit -m "feat(m1): scaffold project with settings, model tiers, llm wrapper"
```

---

### Task 2: 領域模型（Pydantic）與 LangGraph State

**Files:**
- Create: `app/models.py`
- Create: `app/state.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `app.models.Profile`（欄位：`name: str`, `summary: str`, `skills: list[str]`, `experiences: list[str]`, `education: str | None`, `years_experience: float | None`, `preferred_roles: list[str]`, `raw_text: str`）
  - `app.models.ParsedJob`（`title: str`, `company: str`, `location: str | None`, `responsibilities: list[str]`, `required_skills: list[str]`, `nice_to_have: list[str]`, `min_years: float | None`, `tech_stack: list[str]`, `language: str`, `salary: str | None`）
  - `app.models.MatchReport`（`score: int` 0–100, `matched: list[str]`, `gaps: list[str]`, `suggestions: list[str]`, `recommend_proceed: bool`, `reason: str`）
  - `app.state.CopilotState`（TypedDict：`jd_text: str`, `profile: Profile`, `parsed_job: ParsedJob | None`, `match_report: MatchReport | None`）

- [ ] **Step 1: 寫模型的失敗測試**

Create `tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.models import Profile, ParsedJob, MatchReport


def test_profile_minimal_valid():
    p = Profile(name="小明", summary="後端工程師", raw_text="...")
    assert p.skills == []            # 預設空清單
    assert p.years_experience is None


def test_parsed_job_requires_title_and_company():
    with pytest.raises(ValidationError):
        ParsedJob(title="AI 工程師")  # 缺 company


def test_match_report_score_must_be_in_range():
    ok = MatchReport(score=80, recommend_proceed=True, reason="符合度高")
    assert ok.score == 80
    with pytest.raises(ValidationError):
        MatchReport(score=120, recommend_proceed=True, reason="超出範圍")
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_models.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.models'`）

- [ ] **Step 3: 實作 models.py**

Create `app/models.py`:

```python
"""共享領域模型（強型別、可被 with_structured_output 使用）。"""
from pydantic import BaseModel, Field


class Profile(BaseModel):
    """使用者求職背景。"""
    name: str
    summary: str = Field(description="一句話自我介紹/定位")
    skills: list[str] = Field(default_factory=list)
    experiences: list[str] = Field(default_factory=list, description="經歷條列")
    education: str | None = None
    years_experience: float | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    raw_text: str = Field(description="原始貼上的履歷文字")


class ParsedJob(BaseModel):
    """解析後的職缺。"""
    title: str
    company: str
    location: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    min_years: float | None = None
    tech_stack: list[str] = Field(default_factory=list)
    language: str = Field(default="zh", description="JD 主要語言: zh 或 en")
    salary: str | None = None


class MatchReport(BaseModel):
    """匹配評分報告。"""
    score: int = Field(ge=0, le=100, description="0-100 匹配分數")
    matched: list[str] = Field(default_factory=list, description="符合的項目")
    gaps: list[str] = Field(default_factory=list, description="落差/缺少的項目")
    suggestions: list[str] = Field(default_factory=list, description="補強建議")
    recommend_proceed: bool = Field(description="是否建議繼續產出投遞包")
    reason: str = Field(description="建議續做與否的理由")
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_models.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 實作 state.py**

Create `app/state.py`:

```python
"""LangGraph 共享狀態。"""
from typing import TypedDict

from app.models import Profile, ParsedJob, MatchReport


class CopilotState(TypedDict):
    jd_text: str
    profile: Profile
    parsed_job: ParsedJob | None
    match_report: MatchReport | None
```

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/state.py tests/test_models.py
git commit -m "feat(m1): add Pydantic domain models and LangGraph state"
```

---

### Task 3: 測試替身（FakeLLM）與共用 fixtures

**Files:**
- Create: `tests/conftest.py`
- Create: `data/demo_profile.json`

**Interfaces:**
- Produces（給後續測試用）：
  - `tests.conftest.FakeLLM(result)`：模擬 `ChatAnthropic`，其 `.with_structured_output(schema).invoke(messages)` 回傳建構時給的 `result`。
  - pytest fixture `demo_profile() -> Profile`
  - pytest fixture `sample_parsed_job() -> ParsedJob`

- [ ] **Step 1: 建立範例 Profile 資料**

Create `data/demo_profile.json`:

```json
{
  "name": "陳小安",
  "summary": "三年經驗的 Python 後端工程師，近一年投入 LLM 應用開發",
  "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "LangChain", "RAG", "prompt engineering"],
  "experiences": [
    "在電商公司用 FastAPI 開發訂單 API，QPS 提升 3 倍",
    "自建一個 RAG 客服機器人，導入後客服工單下降 25%",
    "用 LangChain 串接內部知識庫，產出問答系統 POC"
  ],
  "education": "資訊工程學系學士",
  "years_experience": 3,
  "preferred_roles": ["AI 工程師", "LLM 應用工程師", "Agent 工程師"],
  "raw_text": "陳小安｜Python 後端 / LLM 應用工程師。三年後端經驗，近一年專注 LLM 與 RAG。技能：Python、FastAPI、PostgreSQL、Docker、LangChain。"
}
```

- [ ] **Step 2: 實作 conftest.py（FakeLLM 與 fixtures）**

Create `tests/conftest.py`:

```python
import json
from pathlib import Path

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
```

- [ ] **Step 3: 驗證 fixtures 可載入**

Create a throwaway check（寫進 `tests/test_models.py` 末尾）：

```python
def test_demo_profile_fixture_loads(demo_profile):
    assert demo_profile.name == "陳小安"
    assert "Python" in demo_profile.skills
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_models.py::test_demo_profile_fixture_loads -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py data/demo_profile.json tests/test_models.py
git commit -m "test(m1): add FakeLLM test double and shared fixtures"
```

---

### Task 4: ① 解析 Agent（parse）

**Files:**
- Create: `app/agents/__init__.py`
- Create: `app/agents/parse.py`
- Create: `data/demo_jobs/ai_engineer.txt`
- Test: `tests/test_parse.py`

**Interfaces:**
- Consumes: `app.llm.get_llm`、`app.models.ParsedJob`
- Produces: `app.agents.parse.parse_job(jd_text: str) -> ParsedJob`

- [ ] **Step 1: 建立範例 JD 資料**

Create `data/demo_jobs/ai_engineer.txt`:

```
【AI 工程師 / LLM 應用工程師】未來智能股份有限公司｜台北

工作內容：
- 開發以 LLM 為核心的應用與 multi-agent 工作流程
- 設計 RAG 檢索流程，串接內部知識庫
- 與後端團隊協作，將 agent 服務以 API 形式上線

必備條件：
- 2 年以上 Python 開發經驗
- 熟悉 LangChain 或 LangGraph 等 agent 框架
- 具備 prompt engineering 與 LLM 應用實作經驗

加分條件：
- 熟悉 FastAPI、Docker
- 有 RAG 或向量資料庫實作經驗

待遇：面議
```

- [ ] **Step 2: 寫解析的失敗測試（用 FakeLLM，確定性）**

Create `tests/test_parse.py`:

```python
from app.models import ParsedJob
from app.agents import parse as parse_mod
from tests.conftest import FakeLLM


def test_parse_job_returns_parsed_job(monkeypatch):
    canned = ParsedJob(
        title="AI 工程師",
        company="未來智能股份有限公司",
        required_skills=["Python", "LangChain"],
        language="zh",
    )
    monkeypatch.setattr(parse_mod, "get_llm", lambda tier: FakeLLM(canned))

    result = parse_mod.parse_job("（任意 JD 文字）")

    assert isinstance(result, ParsedJob)
    assert result.company == "未來智能股份有限公司"
    assert "Python" in result.required_skills


def test_parse_job_uses_cheap_tier(monkeypatch):
    seen = {}
    canned = ParsedJob(title="x", company="y")

    def fake_get_llm(tier):
        seen["tier"] = tier
        return FakeLLM(canned)

    monkeypatch.setattr(parse_mod, "get_llm", fake_get_llm)
    parse_mod.parse_job("jd")
    assert seen["tier"] == "cheap"
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `pytest tests/test_parse.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.agents'`）

- [ ] **Step 4: 實作 parse.py**

Create `app/agents/__init__.py`（空檔），然後 create `app/agents/parse.py`:

```python
"""① 解析 Agent：把 JD 文字抽成結構化 ParsedJob。"""
from app.llm import get_llm
from app.models import ParsedJob

PARSE_SYSTEM = (
    "你是專業的職缺解析器。請從使用者提供的職缺描述（JD）中，"
    "抽取出結構化欄位：職稱、公司、地點、職責、必備條件、加分條件、"
    "最低年資、技術棧、主要語言（zh 或 en）、薪資。"
    "找不到的欄位留空或 null，不要捏造。"
)


def parse_job(jd_text: str) -> ParsedJob:
    """把 JD 文字解析為 ParsedJob（使用 cheap 分層）。"""
    llm = get_llm("cheap").with_structured_output(ParsedJob)
    return llm.invoke(
        [("system", PARSE_SYSTEM), ("human", jd_text)]
    )
```

> 註：測試中 `monkeypatch.setattr(parse_mod, "get_llm", ...)` 取代的是 `parse.py` 模組內的 `get_llm` 名稱，故此處須以 `from app.llm import get_llm` 匯入（而非 `import app.llm`）。

- [ ] **Step 5: 執行測試確認通過**

Run: `pytest tests/test_parse.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: （選用）真打 API 的 live 測試**

Append to `tests/test_parse.py`:

```python
import pytest
from pathlib import Path


@pytest.mark.live
def test_parse_job_live():
    jd = Path("data/demo_jobs/ai_engineer.txt").read_text(encoding="utf-8")
    result = parse_mod.parse_job(jd)
    assert result.title
    assert result.company == "未來智能股份有限公司"
```

Run（需有 API key）：`pytest tests/test_parse.py -m live -v`
Expected: PASS（若略過則顯示 deselected）

- [ ] **Step 7: Commit**

```bash
git add app/agents/__init__.py app/agents/parse.py data/demo_jobs/ai_engineer.txt tests/test_parse.py
git commit -m "feat(m1): add parse agent (JD -> ParsedJob)"
```

---

### Task 5: ② 匹配 Agent（match）

**Files:**
- Create: `app/agents/match.py`
- Test: `tests/test_match.py`

**Interfaces:**
- Consumes: `app.llm.get_llm`、`app.models.ParsedJob`、`app.models.Profile`、`app.models.MatchReport`
- Produces: `app.agents.match.match_profile(job: ParsedJob, profile: Profile) -> MatchReport`

- [ ] **Step 1: 寫匹配的失敗測試（FakeLLM，確定性）**

Create `tests/test_match.py`:

```python
from app.models import MatchReport
from app.agents import match as match_mod
from tests.conftest import FakeLLM


def test_match_profile_returns_report(monkeypatch, demo_profile, sample_parsed_job):
    canned = MatchReport(
        score=82,
        matched=["Python", "LangChain"],
        gaps=["年資略低"],
        suggestions=["補強 multi-agent 專案經驗"],
        recommend_proceed=True,
        reason="技能高度吻合",
    )
    monkeypatch.setattr(match_mod, "get_llm", lambda tier: FakeLLM(canned))

    report = match_mod.match_profile(sample_parsed_job, demo_profile)

    assert isinstance(report, MatchReport)
    assert report.score == 82
    assert report.recommend_proceed is True


def test_match_profile_uses_standard_tier(monkeypatch, demo_profile, sample_parsed_job):
    seen = {}
    canned = MatchReport(score=50, recommend_proceed=False, reason="普通")

    def fake_get_llm(tier):
        seen["tier"] = tier
        return FakeLLM(canned)

    monkeypatch.setattr(match_mod, "get_llm", fake_get_llm)
    match_mod.match_profile(sample_parsed_job, demo_profile)
    assert seen["tier"] == "standard"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_match.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.agents.match'`）

- [ ] **Step 3: 實作 match.py**

Create `app/agents/match.py`:

```python
"""② 匹配 Agent：對 ParsedJob 與 Profile 打分。"""
from app.llm import get_llm
from app.models import ParsedJob, Profile, MatchReport

MATCH_SYSTEM = (
    "你是資深技術招募顧問。請比對『職缺』與『求職者背景』，"
    "給 0-100 的匹配分數，列出符合項、落差項、補強建議，"
    "並判斷是否建議繼續產出投遞包（recommend_proceed）與理由。"
    "評分必須有依據，引用雙方的具體對應點，不要空泛。"
)


def match_profile(job: ParsedJob, profile: Profile) -> MatchReport:
    """比對職缺與求職者，回傳 MatchReport（使用 standard 分層）。"""
    llm = get_llm("standard").with_structured_output(MatchReport)
    human = (
        "【職缺】\n"
        f"{job.model_dump_json(indent=2)}\n\n"
        "【求職者背景】\n"
        f"{profile.model_dump_json(indent=2)}"
    )
    return llm.invoke([("system", MATCH_SYSTEM), ("human", human)])
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_match.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add app/agents/match.py tests/test_match.py
git commit -m "feat(m1): add match agent (job + profile -> MatchReport)"
```

---

### Task 6: Supervisor 圖（串接 + 條件分支）

**Files:**
- Create: `app/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `app.state.CopilotState`、`app.agents.parse.parse_job`、`app.agents.match.match_profile`
- Produces:
  - `app.graph.parse_node(state: CopilotState) -> dict`
  - `app.graph.match_node(state: CopilotState) -> dict`
  - `app.graph.route_after_match(state: CopilotState) -> str`（回傳 `"proceed"` 或 `"stop"`）
  - `app.graph.build_graph()` -> 已 compile 的 LangGraph（可 `.invoke(state)`）

- [ ] **Step 1: 寫圖的失敗測試（注入假 agent，確定性）**

Create `tests/test_graph.py`:

```python
from app.models import ParsedJob, MatchReport
from app import graph as graph_mod


def _patch_agents(monkeypatch, report: MatchReport):
    monkeypatch.setattr(
        graph_mod, "parse_job",
        lambda jd_text: ParsedJob(title="AI 工程師", company="未來智能"),
    )
    monkeypatch.setattr(
        graph_mod, "match_profile",
        lambda job, profile: report,
    )


def test_graph_runs_end_to_end(monkeypatch, demo_profile):
    report = MatchReport(score=82, recommend_proceed=True, reason="吻合")
    _patch_agents(monkeypatch, report)

    app_graph = graph_mod.build_graph()
    final = app_graph.invoke({
        "jd_text": "（任意）",
        "profile": demo_profile,
        "parsed_job": None,
        "match_report": None,
    })

    assert final["parsed_job"].company == "未來智能"
    assert final["match_report"].score == 82


def test_route_after_match_proceeds_on_high_score():
    state = {"match_report": MatchReport(score=80, recommend_proceed=True, reason="高")}
    assert graph_mod.route_after_match(state) == "proceed"


def test_route_after_match_stops_when_not_recommended():
    state = {"match_report": MatchReport(score=40, recommend_proceed=False, reason="低")}
    assert graph_mod.route_after_match(state) == "stop"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_graph.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.graph'`）

- [ ] **Step 3: 實作 graph.py**

Create `app/graph.py`:

```python
"""Supervisor 骨架：parse -> match -> 條件分支。

M1 中兩條分支都指向 END（fan-out 屬 M2）；route_after_match 的決策邏輯
先建立好，M2 只需把 "proceed" 改接到 fan-out 節點。
"""
from langgraph.graph import StateGraph, START, END

from app.state import CopilotState
from app.agents.parse import parse_job
from app.agents.match import match_profile


def parse_node(state: CopilotState) -> dict:
    return {"parsed_job": parse_job(state["jd_text"])}


def match_node(state: CopilotState) -> dict:
    report = match_profile(state["parsed_job"], state["profile"])
    return {"match_report": report}


def route_after_match(state: CopilotState) -> str:
    """依匹配結果決定續做或收手。"""
    report = state["match_report"]
    return "proceed" if report.recommend_proceed else "stop"


def build_graph():
    g = StateGraph(CopilotState)
    g.add_node("parse", parse_node)
    g.add_node("match", match_node)
    g.add_edge(START, "parse")
    g.add_edge("parse", "match")
    g.add_conditional_edges(
        "match",
        route_after_match,
        {"proceed": END, "stop": END},  # M2 會把 proceed 改接 fan-out
    )
    return g.compile()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_graph.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add app/graph.py tests/test_graph.py
git commit -m "feat(m1): wire supervisor graph (parse -> match -> route)"
```

---

### Task 7: CLI 進入點 + 完整流程

**Files:**
- Create: `app/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `app.graph.build_graph`、`app.models.Profile`、`app.models.MatchReport`
- Produces:
  - `app.cli.load_profile(path: str = "data/demo_profile.json") -> Profile`
  - `app.cli.format_report(report: MatchReport, job_title: str) -> str`
  - `app.cli.run(jd_path: str, profile_path: str = "data/demo_profile.json") -> MatchReport`
  - `app.cli.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: 寫 CLI 的失敗測試（注入假圖，確定性）**

Create `tests/test_cli.py`:

```python
from pathlib import Path

from app.models import ParsedJob, MatchReport
from app import cli as cli_mod


def test_load_profile_reads_demo(tmp_path):
    p = cli_mod.load_profile("data/demo_profile.json")
    assert p.name == "陳小安"


def test_format_report_contains_score_and_reason():
    report = MatchReport(
        score=82, matched=["Python"], gaps=["年資"],
        suggestions=["補強 X"], recommend_proceed=True, reason="吻合",
    )
    text = cli_mod.format_report(report, job_title="AI 工程師")
    assert "82" in text
    assert "吻合" in text
    assert "AI 工程師" in text


def test_run_invokes_graph(monkeypatch, tmp_path):
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("一些 JD", encoding="utf-8")

    fake_final = {
        "parsed_job": ParsedJob(title="AI 工程師", company="未來智能"),
        "match_report": MatchReport(score=70, recommend_proceed=True, reason="ok"),
    }

    class FakeGraph:
        def invoke(self, state):
            return fake_final

    monkeypatch.setattr(cli_mod, "build_graph", lambda: FakeGraph())

    report = cli_mod.run(str(jd_file))
    assert report.score == 70
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.cli'`）

- [ ] **Step 3: 實作 cli.py**

Create `app/cli.py`:

```python
"""終端機進入點：讀 JD → 跑圖 → 印匹配報告。"""
import json
import sys
from pathlib import Path

from app.models import Profile, MatchReport
from app.graph import build_graph


def load_profile(path: str = "data/demo_profile.json") -> Profile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Profile(**data)


def format_report(report: MatchReport, job_title: str) -> str:
    lines = [
        f"=== 匹配報告：{job_title} ===",
        f"分數：{report.score}/100",
        f"建議續做：{'是' if report.recommend_proceed else '否'}（{report.reason}）",
        "",
        "符合項：" + ("、".join(report.matched) or "（無）"),
        "落差項：" + ("、".join(report.gaps) or "（無）"),
        "補強建議：" + ("、".join(report.suggestions) or "（無）"),
    ]
    return "\n".join(lines)


def run(jd_path: str, profile_path: str = "data/demo_profile.json") -> MatchReport:
    jd_text = Path(jd_path).read_text(encoding="utf-8")
    profile = load_profile(profile_path)
    graph = build_graph()
    final = graph.invoke({
        "jd_text": jd_text,
        "profile": profile,
        "parsed_job": None,
        "match_report": None,
    })
    return final["match_report"]


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("用法：python -m app.cli <jd 檔案路徑>")
        return 1
    jd_path = argv[0]
    report = run(jd_path)
    title = Path(jd_path).stem
    print(format_report(report, job_title=title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_cli.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 跑整套測試**

Run: `pytest`
Expected: 全部 PASS（live 測試 deselected）

- [ ] **Step 6: （選用）真打 API 的端到端手動驗證**

Run（需 `.env` 內有 `ANTHROPIC_API_KEY`）：

```bash
python -m app.cli data/demo_jobs/ai_engineer.txt
```

Expected: 印出含分數、建議續做、符合/落差/建議的匹配報告。

- [ ] **Step 7: Commit**

```bash
git add app/cli.py tests/test_cli.py
git commit -m "feat(m1): add CLI entrypoint and end-to-end run"
```

---

## Self-Review（對照規格檢查）

**1. Spec coverage（M1 範圍）：**
- supervisor 骨架 → Task 6 ✓
- ① 解析 → Task 4 ✓
- ② 匹配 → Task 5 ✓
- 分數門檻決策（supervisor 提早收手）→ Task 6 `route_after_match` ✓
- 模型分層 → Task 1 `settings.py` + 各 agent 指定 tier ✓
- 結構化輸出（Pydantic）→ Task 2 + `with_structured_output` ✓
- 終端機可跑 + demo 資料集 → Task 7 + `data/` ✓
- 測試與（基礎）eval 思維 → 每個 agent 有確定性測試 + live 測試骨架 ✓
- LangSmith 追蹤 → `.env.example` 預留環境變數（LangChain 自動上報）✓
- （M2+ 才做：fan-out、Critic、human-in-the-loop、公司情報、URL 抓取、前端、FastAPI）→ 已明確排除 ✓

**2. Placeholder scan：** 無 TBD/TODO；每個 code step 皆有完整可執行程式碼。✓

**3. Type consistency：** `get_llm(tier)`、`parse_job(jd_text) -> ParsedJob`、`match_profile(job, profile) -> MatchReport`、`build_graph()`、`route_after_match -> "proceed"/"stop"`、`CopilotState` 欄位於各 task 一致；測試對 `parse_mod.get_llm` / `match_mod.get_llm` 的 monkeypatch 與實作的 `from app.llm import get_llm` 匯入方式相符。✓

無發現缺漏，無需追加任務。
