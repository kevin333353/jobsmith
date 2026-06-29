<div align="center">

<img src="https://raw.githubusercontent.com/kevin333353/jobsmith/master/frontend/public/logo512.png" alt="Jobsmith logo" width="84" height="84" />

# Jobsmith

**針對台灣求職市場的開源多代理（multi-agent）AI 求職 co-pilot。**

找職缺、履歷健檢、產生客製投遞包（履歷・求職信・面試準備・公司情報）、模擬面試。產生投遞包是**背景工作**（離開頁面或重新整理都不中斷，還能多個職缺平行跑）；看完多 agent 即時編排，再到「我的投遞包」逐一核可。

預設用你本機的 **Claude Code / Codex CLI 訂閱**當 AI 引擎（**免自行申請 API key**），也能改用 **Ollama / llama.cpp 本機模型**，或**自備金鑰**接任何 OpenAI 相容模型。

[English](README.en.md) · [**下載（Windows / macOS unsigned）**](#下載) · [快速開始](#快速開始從原始碼) · [系統架構](#系統架構) · [隱私](docs/PRIVACY.md)

![License](https://img.shields.io/badge/License-Apache_2.0-green)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Platform](https://img.shields.io/badge/Windows-64--bit-0078D6?logo=windows&logoColor=white)
![Platform](https://img.shields.io/badge/macOS-unsigned-lightgrey?logo=apple)

</div>

> 應用程式介面為繁體中文，貼合台灣求職生態（104 / Cake / Yourator / LinkedIn）。資料以本機保存為主；執行 AI 功能時，履歷與 prompt 會交給你選擇的 CLI、本機模型或 BYOK 後端處理。詳見 [隱私與資料處理](docs/PRIVACY.md)。

---

## 功能概覽

- **自動找職缺**：上傳履歷後由 AI 推導關鍵字，搜尋 104 / Yourator / LinkedIn / Cake。
- **職缺評分排序**：分批串流職缺、評估適配度，並可直接進入投遞包流程。
- **投遞工作包**：產出客製履歷、求職信、面試準備與公司研究。
- **履歷健檢**：檢查 ATS 與內容完整度，標示深度健檢或備援健檢，並保留本機歷史紀錄。

---

## 下載

**Windows**

**[⬇ 下載 Jobsmith for Windows（64 位元）](https://github.com/kevin333353/jobsmith/releases/latest/download/Jobsmith.exe)** — 單一 `.exe`，免裝 Python / Node.js。

1. 從 [最新 release](https://github.com/kevin333353/jobsmith/releases/latest) 下載 `Jobsmith.exe`。
2. 雙擊開啟，會跳出原生視窗（第一次啟動會解壓約 10–30 秒）。
3. 在**右上角控制台**選你的 AI 引擎：
   - **本機 CLI**——PATH 上已登入的 **Claude Code**（`claude`）或 **Codex CLI**（`codex`），或
   - **本機模型**——已啟動的 **Ollama**（預設 `http://127.0.0.1:11434/v1`）或 **llama.cpp server**（預設 `http://127.0.0.1:8080/v1`），或
   - **BYOK**——填 `base_url` + `api_key` + `model` 接任何 OpenAI 相容端點（OpenAI、DeepSeek、Gemini、Groq、OpenRouter、Ollama、LM Studio、vLLM…）。

> **需求：** Windows 10/11（64 位元；WebView2 為 Windows 11 內建）。歷史、設定、`.env` 都存在 exe 旁邊；Jobsmith 不營運 hosted backend，AI 請求只會送到你選擇的後端。

**macOS**

- **[⬇ 下載 Jobsmith for macOS Apple Silicon](https://github.com/kevin333353/jobsmith/releases/latest/download/Jobsmith-macOS-arm64-unsigned.dmg)** — M1 / M2 / M3 / M4
- **[⬇ 下載 Jobsmith for macOS Intel](https://github.com/kevin333353/jobsmith/releases/latest/download/Jobsmith-macOS-x64-unsigned.dmg)** — Intel Mac

macOS 目前是 **unsigned** `.dmg`，尚未做 Apple Developer ID 簽章與 notarization。第一次開啟可能被 Gatekeeper 擋下，請打開 DMG 後將 `Jobsmith.app` 拖到 Applications，再右鍵 `Jobsmith.app` →「打開」，或到系統設定允許。

macOS 版資料與 `.env` 會存在 `~/Library/Application Support/Jobsmith`。

開發者可到 GitHub **Actions → Build unsigned macOS DMG** 手動重打 macOS 發佈檔；workflow 提供 `publish_release=true` 選項，可把 DMG 覆蓋到指定 release tag。

## 快速開始（從原始碼）

> **環境需求：** Python 3.11+、Node.js 20.19+ / 22.13+ / 24+，以及 PATH 上已登入的 **Claude Code**（`claude`）或 **Codex CLI**（`codex`）、本機 Ollama/llama.cpp server，或一組 BYOK 金鑰。

```bash
git clone https://github.com/kevin333353/jobsmith.git
cd jobsmith

setup.bat            # Windows  — 一鍵安裝（venv + 相依 + 前端建置）
# ./setup.sh         # macOS / Linux / Git Bash

desktop.bat          # 以原生桌面視窗啟動（推薦）
# run.bat            # 或網頁版 → http://localhost:8000
```

| 模式           | 指令                                                          | 說明                                       |
| -------------- | ------------------------------------------------------------- | ------------------------------------------ |
| **桌面 App**   | `desktop.bat`（或 `python desktop.py`）                       | 原生視窗；第一次會有後端選擇。             |
| **網頁版**     | `run.bat`（或 `python -m uvicorn app.server:app --port 8000`） | 開 <http://localhost:8000>。               |
| **CLI（單一 JD）** | `python -m app.cli data/demo_jobs/ai_engineer.txt`        | 無介面、單一 JD 跑一次。                   |

自己打包 Windows `.exe`：`pip install pyinstaller && pyinstaller jobsmith.spec --noconfirm` → `dist/Jobsmith.exe`。
macOS unsigned `.app` 請在 macOS 上先建置前端，再執行：`python -m PyInstaller jobsmith-macos.spec --noconfirm --clean` → `dist/Jobsmith.app`。

## 目錄

- [功能概覽](#功能概覽)
- [下載](#下載)
- [快速開始](#快速開始從原始碼)
- [功能](#功能)
- [LLM 後端](#llm-後端)
- [隱私與資料](#隱私與資料)
- [系統架構](#系統架構)
- [成效評測](#成效評測)
- [技術棧](#技術棧)
- [專案結構](#專案結構)
- [測試](#測試)
- [Roadmap](#roadmap)
- [貢獻](#貢獻)
- [免責聲明](#免責聲明)
- [授權](#授權)

## 功能

- **自動找職缺**：貼上或上傳履歷 → AI 推導關鍵字 → **並行**搜尋 104 / Yourator / LinkedIn / Cake → **分批串流**依適配度排序（邊評邊顯示）。可在**搜尋前先選縣市**（104 於來源端篩、其餘來源於結果端篩）、依**適配色帶**（高／中以上／全部）篩選、調整每來源頁數，並把指定公司的開缺列在獨立區塊。
- **搜尋紀錄**：每次搜尋自動存整包，可回看、重新產生投遞包、刪除——不怕好職缺重找就不見。
- **履歷健檢**：依台灣 ATS 慣例評分，給具體修改建議與改寫前後範例。
- **投遞包工作台**：對任一職缺按「產生投遞包」，多代理流程（解析 JD → 匹配評分 → 公司情報 → 客製履歷 → 求職信 → 面試準備 → 品管反思）在**背景**執行——離開頁面或重新整理都不中斷，多個職缺還能**平行**跑。畫面乾淨一頁式：左側即時多代理編排、右側分頁瀏覽成品。
- **我的投遞包**：每份產生的投遞包都會進這裡，並標示狀態（進行中 → 待審 → 已核可）。可**核可、刪除**、重新開到工作台、用它開模擬面試，並匯出 **Word（.docx）**（PDF 透過瀏覽器列印）。
- **模擬面試**：依 JD 與你的履歷出題，逐題即時回饋與評分。可從任一份投遞包或貼 JD 開始；**每個職缺各自一個對話分頁**，可同時跑多場、互不覆蓋。
- **個人化**：跨 session 記住最近履歷（免重傳）與偏好（目標職稱／語氣／想強調技能），並套用到產出。

## LLM 後端

從**右上角控制台**選你的 AI 引擎——**本機 CLI 訂閱**（免 API key）、**本機模型**（Ollama / llama.cpp）或 **BYOK**（任何 OpenAI 相容端點）。選了即生效；「測試」只是選用的連線檢查、非門檻。本機 CLI 可**重新掃描**、並可**自選模型**：

| 後端         | 認證方式                          | 說明                                                                                  |
| ------------ | --------------------------------- | ------------------------------------------------------------------------------------- |
| `claude_cli` | Claude Code 訂閱                  | **預設。** 免 API key；會移除 `ANTHROPIC_*` 環境變數。模型可自選（預設自動分層）。     |
| `codex_cli`  | Codex 訂閱                        | 免 API key。模型可自選；預設沿用你的 Codex 設定。                                      |
| `ollama`     | 本機模型                          | 預設支援 Ollama；也可切到 llama.cpp server 或自訂本機 OpenAI-compatible endpoint。可重新偵測本機模型並以下拉選擇；品質與速度取決於本機硬體與模型。 |
| `openai`     | BYOK——任何 OpenAI 相容端點        | `base_url` + `api_key` + `model`。可接 OpenAI、DeepSeek、Gemini、Groq、OpenRouter、Ollama、LM Studio、vLLM…  |

CLI 後端會透過你機器上已登入的 CLI 呼叫對應 provider；本機模型與 BYOK 都走 OpenAI-compatible endpoint。Jobsmith 不提供 hosted backend，也不把資料送到專案作者的伺服器。BYOK 與本機模型設定只寫進你本機的 `.env`。另有 API key 後端（`anthropic`）供自架或 CI 使用。

## 隱私與資料

Jobsmith 會在本機保存履歷記憶、偏好、搜尋紀錄、投遞包、`.env` 與錯誤紀錄。你可以在 **設定 → 清除個人資料** 清掉履歷記憶、搜尋紀錄與投遞包；AI 後端設定會保留，避免重填 API key。

執行 AI 功能時，履歷、職缺描述與 prompt 會送到你選擇的 AI 後端。請先閱讀 [隱私與資料處理](docs/PRIVACY.md)。

## 系統架構

```
React SPA (Vite)  ──HTTP · SSE · 輪詢──►  FastAPI
                                          │
                  ┌───────────────────────┼───────────────────────┐
                  ▼                       ▼                      ▼
        LangGraph StateGraph         職缺來源              App SQLite
        (每個背景產生一個、各自         104 / Yourator /     (投遞包＋狀態
         記憶體 checkpointer、可平行)   LinkedIn / Cake       進行中→待審→已核可、
                  │                                          記憶、搜尋)
                  ▼
          可切換的 LLM 後端
          claude_cli · codex_cli · ollama (local) · openai (BYOK)
```

- **背景產生**：每次「產生投遞包」都開一個獨立的 LangGraph `StateGraph` ＋私有記憶體 checkpointer，丟到小型執行緒池跑——所以可**平行**、且不受瀏覽器斷線（重新整理／切頁）影響；前端**輪詢** `/api/run/events` 看即時進度，跑完寫進應用層資料庫。關掉分頁也不會中斷。
- **自動找職缺**以 **Server-Sent Events** 邊搜、邊評、邊串流回瀏覽器。
- 應用層 SQLite 存放投遞包（含生命週期狀態：進行中 → 待審 → 已核可）、使用者記憶與搜尋紀錄；在「我的投遞包」核可。_（獨立的 CLI 仍保留可續跑、檔案型的人工核可關卡：`interrupt()` / `Command(resume=…)`。）_
- CLI 後端下模型自動分層：解析用 **haiku**、匹配／生成用 **sonnet**、深思（Critic/Supervisor）用 **opus**（可於各後端覆寫）。

## 成效評測

Supervisor 反思迴圈（Critic → 重寫未過文件 → 再評）到底有沒有提升品質？用 5 組職缺／履歷的 golden set，分別在反思**關**（不重寫）與**開**兩種設定下跑，比較 Critic 分數：

<!-- EVAL:START -->
| 反思 | Critic 通過率 | 平均品質分數 |
| ---- | ------------- | ------------ |
| 關   | 60%（3/5）    | 85.6         |
| **開** | **100%（5/5）** | **87.5**   |

反思讓 Critic 通過率提升 **+40 個百分點**（60% → 100%）、平均品質 **+1.9**（85.6 → 87.5）。關閉反思時的兩個失敗案例，都是求職信出現**未經查證的公司事實**或**履歷未支持的經歷宣稱**——正是 Critic → 重寫迴圈會抓出來的問題。_（單次 harness 執行；LLM 呼叫非確定性，實際數字每次略有不同。）_
<!-- EVAL:END -->

```bash
python -m app.evals.harness     # 對每個 golden 案例跑整張 graph，寫入 app/evals/results.json
```

彙整用的 `summarize()` 是純函式、有獨立單元測試，因此聚合邏輯不受（非確定性的）LLM 呼叫影響、可單獨驗證。

## 技術棧

| 層級     | 技術                                                                       |
| -------- | -------------------------------------------------------------------------- |
| 後端     | Python、FastAPI、LangGraph、LangChain、Pydantic v2、SQLite、BeautifulSoup   |
| 前端     | React 19、TypeScript、Vite、Tailwind CSS、lucide-react                      |
| LLM      | Claude Code CLI / Codex CLI（本機）· Ollama / llama.cpp 本機模型 · 任何 OpenAI 相容端點（BYOK） |
| 桌面     | pywebview（原生視窗）· PyInstaller（單檔 `.exe` / unsigned `.app`，macOS 以 `.dmg` 發佈） |

## 專案結構

```
app/
  agents/     # 履歷健檢、職缺搜尋、公司情報、文件對話、面試模擬…
  sources/    # 104 / Yourator / LinkedIn / Cake 搜尋 + registry + 縣市對應
  store/      # 應用層 SQLite：歷史、記憶、搜尋紀錄
  intake/     # 履歷／JD 解析與抓取
  export/     # Word（.docx）匯出
  graph.py    # LangGraph StateGraph（代理 + 人工核可）
  server.py   # FastAPI + SSE 端點
  llm.py      # 可切換 LLM 後端
frontend/     # Vite + React + TS + Tailwind 前端
tests/        # pytest 測試
desktop.py    # 原生視窗啟動器      jobsmith.spec / jobsmith-macos.spec  # PyInstaller 打包
```

## 測試

```bash
pytest                         # 單元/整合測試（預設略過 live API 測試）
pytest -m live                 # 含真打 API 的測試
cd frontend && npm run lint    # 前端 lint
cd frontend && npm run build   # 型別檢查 + 正式建置
```

## Roadmap

- [x] 單檔 Windows 桌面 App（PyInstaller）
- [x] unsigned macOS `.dmg` GitHub Actions build
- [x] BYOK——任何 OpenAI 相容後端
- [x] Ollama / llama.cpp 本機模型後端
- [x] 背景、可平行、重新整理不中斷的投遞包產生
- [ ] macOS 簽章與 notarization
- [ ] Linux 版本
- [ ] 更多職缺來源

## 貢獻

歡迎 issue 與 pull request。較大的變更請先開 issue 討論方向。提交前請跑 `pytest`、`npm run lint` 與 `npm run build`。發佈 Windows `.exe` 前請照 [Release Checklist](docs/RELEASE_CHECKLIST.md) 做一次乾淨環境 smoke test。

## 免責聲明

本專案僅供**個人、教育與研究用途**，以低頻方式查詢 104 / Yourator / LinkedIn / Cake 的公開職缺，協助個別求職者。使用者需自行遵守各網站的服務條款與 `robots.txt`，**請勿**用於大量爬取或商業性資料蒐集。軟體按「現狀」提供，不附任何擔保。AI 生成內容（履歷、求職信、公司情報）可能有誤，使用前請務必自行檢視。

## 授權

採用 [Apache License 2.0](LICENSE)。
