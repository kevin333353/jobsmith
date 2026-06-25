<div align="center">

# 台灣 AI 求職 Co-pilot

**針對台灣求職市場的多代理（multi-agent）求職助理 — 找職缺、履歷健檢、客製投遞包、模擬面試，一條龍。**

預設用你本機的 **Claude Code / Codex CLI 訂閱**當 AI 引擎，**免 API key、不吃 API 額度**。

[English](README.md) · **繁體中文**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3-06B6D4?logo=tailwindcss&logoColor=white)

</div>

> 應用程式介面為繁體中文，貼合台灣求職生態（104 / Cake / Yourator / LinkedIn）。

## 快速開始

> **環境需求：** Python 3.11+、Node.js 18+，以及下列擇一：PATH 上已登入的 **Claude Code**（`claude`）／ **Codex CLI**（`codex`），或一組 **Anthropic API key**。

```bash
git clone https://github.com/kevin333353/taiwan-ai-job-copilot.git
cd taiwan-ai-job-copilot

# 一鍵安裝：venv + 後端相依 + 前端安裝與建置
setup.bat            # Windows
# ./setup.sh         # macOS / Linux / Git Bash

# 啟動
desktop.bat          # 原生桌面視窗（推薦）
# run.bat            # 網頁版 → http://localhost:8000
```

`setup.bat` / `setup.sh` 會一次做完所有事（建 venv、`pip install`、`npm install`、`npm run build`）——**不必自己分別開前後端安裝與啟動**。

要改用 **API key** 後端（而非 CLI 訂閱）？把 `.env.example` 複製成 `.env` 並設定：

```env
LLM_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### 執行模式

| 模式           | 指令                                                          | 說明                                       |
| -------------- | ------------------------------------------------------------- | ------------------------------------------ |
| **桌面 App**   | `desktop.bat`（或 `python desktop.py`）                       | 原生視窗；第一次會有後端選擇 + 連線測試。  |
| **網頁版**     | `run.bat`（或 `python -m uvicorn app.server:app --port 8000`） | 開 <http://localhost:8000>。               |
| **CLI（單一 JD）** | `python -m app.cli data/demo_jobs/ai_engineer.txt`        | 無介面、單一 JD 跑一次。                   |

> 後端切換：開場引導畫面、右上角選單，或 `.env` 的 `LLM_BACKEND` 皆可。

## 目錄

- [快速開始](#快速開始)
- [功能](#功能)
- [LLM 後端](#llm-後端)
- [系統架構](#系統架構)
- [技術棧](#技術棧)
- [專案結構](#專案結構)
- [測試](#測試)
- [Roadmap](#roadmap)
- [貢獻](#貢獻)
- [授權](#授權)

## 功能

- **自動找職缺**：貼上或上傳履歷 → AI 推導關鍵字 → **並行**搜尋 104 / Yourator / LinkedIn / Cake → **分批串流**依適配度排序（邊評邊顯示）。附「只看 ≥ N 分」滑桿、分頁，以及可指定公司名單的獨立開缺區塊。
- **技能缺口分析**：彙整搜到職缺常見要求技能，對照你的履歷，找出真正的缺口。
- **搜尋紀錄**：每次搜尋自動存整包（AI 推薦＋指定公司＋技能缺口），可回看、重新產生投遞包、刪除——不怕好職缺重找就不見。
- **履歷健檢**：依台灣 ATS 慣例評分，給具體修改建議與改寫前後範例。
- **投遞包工作台**：多代理流程（解析 JD → 匹配評分 → 公司情報 → 客製履歷 → 求職信 → 面試準備 → 品管反思），中途**人工核可**；成品可線上編輯、匯出 Word / PDF，完成自動存進「我的投遞包」。
- **模擬面試**：依 JD 與你的履歷出題，逐題即時回饋與評分 + 總評。
- **個人化**：跨 session 記住最近履歷（免重傳）與偏好（目標職稱／語氣／想強調技能），並套用到產出。

## LLM 後端

| 後端         | 認證方式                  | 說明                                       |
| ------------ | ------------------------- | ------------------------------------------ |
| `claude_cli` | Claude Code 訂閱          | **預設。** 免 API key；會移除 `ANTHROPIC_*` 環境變數。 |
| `codex_cli`  | Codex 訂閱                | 使用你設定的 Codex 模型。                  |
| `anthropic`  | `ANTHROPIC_API_KEY`       | 可雲端部署；按量計費。                     |

CLI 訂閱是在**本機**執行、綁定你機器上登入的 CLI——遠端伺服器無法使用別人本機的訂閱。若要做完全託管的雲端版，請改用 `anthropic` 後端。

## 系統架構

```
React SPA (Vite)  ──HTTP/SSE──►  FastAPI
                                   │
                  ┌────────────────┼─────────────────────┐
                  ▼                ▼                     ▼
          LangGraph StateGraph   職缺來源            App SQLite
          (代理 + 人工核可)       104/Yourator/      (歷史 /
          SqliteSaver checkpoint  LinkedIn/Cake      記憶 / 搜尋)
                  │
                  ▼
          可切換的 LLM 後端
          claude_cli · codex_cli · anthropic
```

- 以 LangGraph `StateGraph` 編排各代理；`SqliteSaver` 保存 checkpoint，並以 `interrupt()` / `Command(resume=…)` 實作 human-in-the-loop 核可。
- 伺服器以 **Server-Sent Events** 將進度串流到瀏覽器。
- 應用層 SQLite（與 LangGraph checkpoint 分開）存放投遞包歷史、使用者記憶與搜尋紀錄。
- 模型自動分層：解析用 **haiku**、匹配／生成用 **sonnet**、深思（Critic/Supervisor）用 **opus**。

## 技術棧

| 層級     | 技術                                                                     |
| -------- | ------------------------------------------------------------------------ |
| 後端     | Python、FastAPI、LangGraph、LangChain、Pydantic v2、SQLite、BeautifulSoup |
| 前端     | React 19、TypeScript、Vite、Tailwind CSS、lucide-react                    |
| LLM      | Claude Code CLI / Codex CLI（訂閱）· Anthropic API（金鑰）                |
| 桌面     | pywebview（在本機伺服器上開原生視窗）                                     |

## 專案結構

```
app/
  agents/     # 履歷健檢、職缺搜尋、公司情報、技能缺口、面試模擬…
  sources/    # 104 / Yourator / LinkedIn / Cake 搜尋 + registry
  store/      # 應用層 SQLite：歷史、記憶、搜尋紀錄
  intake/     # 履歷／JD 解析與抓取
  export/     # Word/PDF 匯出
  graph.py    # LangGraph StateGraph（代理 + 人工核可）
  server.py   # FastAPI + SSE 端點
  llm.py      # 可切換 LLM 後端
frontend/     # Vite + React + TS + Tailwind 前端
tests/        # pytest 測試
data/         # demo 履歷/職缺、後備資料
```

## 測試

```bash
pytest                # 單元/整合測試（預設略過 live API 測試）
pytest -m live        # 含真打 API 的測試
cd frontend && npm run build   # 型別檢查 + 正式建置
```

## Roadmap

- [ ] 單檔桌面執行檔（PyInstaller），讓沒裝開發環境的人也能用
- [ ] 託管版（使用者自帶 API key）部署模式
- [ ] 更多職缺來源

## 貢獻

歡迎 issue 與 pull request。較大的變更請先開 issue 討論方向。提交前請跑 `pytest` 與 `npm run build`。

## 授權

目前尚未選定授權條款。在加入 `LICENSE` 檔之前，作者保留一切權利。
