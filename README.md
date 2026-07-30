<div align="center">

<img src="https://raw.githubusercontent.com/kevin333353/jobsmith/master/frontend/public/logo512.png" alt="Jobsmith logo" width="84" height="84" />

# Jobsmith

**針對台灣求職市場的開源多代理（multi-agent）AI 求職 co-pilot。**

找職缺、履歷健檢、按需產生客製投遞文件（履歷・求職信・面試準備・公司情報）、模擬面試。產出是**背景工作**（離開頁面或重新整理都不中斷，還能多個職缺平行跑）；看完本次實際執行的步驟，再到「我的投遞包」逐一核可。

預設用你本機的 **Claude Code / Codex CLI 訂閱**當 AI 引擎（**免自行申請 API key**），也能改用 **Ollama / llama.cpp 本機模型**，或**自備金鑰**接任何 OpenAI 相容模型。

**如果這個工具對你找工作或研究 AI Agent 有幫助，歡迎按 Star 支持開源。**

[English](README.en.md) · [**手機 Web（免 AI、免安裝）**](https://jobsmith-web.onrender.com) · [**下載桌面版（Windows / macOS unsigned）**](#下載) · [快速開始](#快速開始從原始碼) · [系統架構](#系統架構) · [隱私](docs/PRIVACY.md)

![License](https://img.shields.io/badge/License-Apache_2.0-green)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Platform](https://img.shields.io/badge/Windows-64--bit-0078D6?logo=windows&logoColor=white)
![Platform](https://img.shields.io/badge/macOS-unsigned-lightgrey?logo=apple)

</div>

> 應用程式介面為繁體中文，貼合台灣求職生態（104 / Cake / Yourator / LinkedIn）。預設的「免 AI 找職缺」不需要 AI 帳號或 API key；資料以本機保存為主。只有明確選用 AI 功能時，履歷與 prompt 才會交給你選擇的 CLI、本機模型或 BYOK 後端處理。詳見 [隱私與資料處理](docs/PRIVACY.md)。
>
> 另提供手機可用的**公開 Web 測試模式**：免帳號、強制 0 AI、不保存伺服器端履歷／搜尋紀錄，只開放上傳履歷找職缺與瀏覽器端篩選。[立即開啟 Jobsmith Web](https://jobsmith-web.onrender.com)，部署與限制請見 [公開 Web 測試版部署](docs/WEB_DEPLOYMENT.md)。

---

## Web（免 AI、免安裝）

**[📱 立即開啟 Jobsmith Web](https://jobsmith-web.onrender.com)**

不用安裝 App、不用 AI 帳號，也不需要 API key。公開 Web 測試版支援：

- 手機上傳 PDF、DOCX 或 TXT 履歷，先確認並自由修改目標職稱。
- 以 0 AI 本機規則搜尋 104、Cake、Yourator、LinkedIn 等來源，顯示可解釋配對與市場技能雷達。
- 在目前結果中依關鍵字、地點、來源、遠端型態、適配度、年資與薪資即時篩選，不必重新搜尋。
- 多人同時使用時自動排隊；相同搜尋範圍會短期共用公開職缺來源快取，減少等待與第三方網站負載。

公開站不建立帳號，也不把履歷、Profile、個人配對結果或搜尋紀錄寫入伺服器資料庫；短期共用快取只包含搜尋關鍵字／範圍與公開職缺資料。完整履歷會送到 Jobsmith Web 伺服器做該次解析，因此仍建議先移除電話、Email 與地址等不必要欄位。站方可選擇啟用不含履歷／搜尋內容的伺服器端匿名流量與轉換事件；桌面版不啟用。詳細資料流向請見[隱私說明](docs/PRIVACY.md)，站方設定方式見[匿名使用分析](docs/PRODUCT_ANALYTICS.md)。

目前使用免費測試主機，閒置後第一次開啟可能需要約一分鐘喚醒，尖峰時會顯示排隊順位。需要 AI 投遞包、履歷健檢、面試模擬或長期本機紀錄時，請使用下方桌面版。

---

## 功能概覽

- **免 AI 找職缺**：上傳履歷後在本機辨識職稱、技能與年資；搜尋前可確認或改寫最多三個目標職稱，即使不在內建詞庫也會照原文搜尋。免 AI 帳號、免 API key、0 token。
- **[手機 Web 入口](https://jobsmith-web.onrender.com)**：公開模式只提供履歷辨識、找職缺、即時結果篩選與前往原職缺；桌面私有資料與 AI API 全部封鎖。
- **可解釋職缺配對**：以職稱、技能、年資規則排序，分開標示適配度與職缺資料完整度，並列出符合點、待確認缺口及市場技能雷達。
- **跨職類但不假裝全知**：內建常見科技、商務、行政、零售、餐旅、物流、製造、營建、醫護、教育、法律與服務業職稱；辨識不準時由使用者直接修正，不把未知職業硬套成工程師。
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

> **需求：** Windows 10/11（64 位元；WebView2 為 Windows 11 內建）。桌面版歷史、設定、`.env` 都存在 exe 旁邊；AI 請求只會送到你選擇的後端。功能受限的公開 Web 測試版另見[隱私說明](docs/PRIVACY.md)。

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

- [手機 Web（免 AI、免安裝）](#手機-web免-ai免安裝)
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

- **自動找職缺**：預設選用「免 AI」——貼上或上傳履歷 → 在真正搜尋前確認／修改目標職稱 → 本機規則辨識技能與年資 → 產生中英文職稱搜尋詞 → **並行**搜尋 104 / Yourator / LinkedIn / Cake → **分批串流**可解釋的適配排序。其他搜尋條件預設收合且全部可略過；需要時再展開縣市、完全遠端／部分遠端，或第二層的年資、薪資、指定公司與搜尋深度。遠端條件預設只接受網站明確標示，也可自行開啟 JD 文字推測。結果出現後，可直接在目前資料池依關鍵字、地點、來源、工作型態、適配度、年資與薪資即時縮小結果，不必重新搜尋或呼叫 AI。
- **市場技能雷達**：從目前高度適配的職缺彙整常見技能，分開顯示履歷已具備與待補強項目；這是確定性統計，不呼叫 LLM，也不會把來源未標示的技能當成缺口。
- **搜尋紀錄**：每次搜尋自動存整包，可回看、套用與目前結果相同的本地篩選、重新產生投遞包或刪除——不怕好職缺重找就不見。
- **履歷健檢**：依台灣 ATS 慣例評分，給具體修改建議與改寫前後範例。
- **投遞包工作台**：預設「快速投遞」只做客製履歷，也可選「完整申請」「面試準備」或自行勾選文件；公司情報與 AI 品管皆為選配。搜尋結果會沿用已完成的職缺分析，AI 品管只提供一次修改建議、**不自動重寫**。整個流程在**背景**執行——離開或重新整理都不中斷，多個職缺還能平行跑；左側只顯示本次會執行的步驟，右側分頁瀏覽成品。
- **我的投遞包**：每份產生的投遞包都會進這裡，並標示狀態（進行中 → 待審 → 已核可）。可**核可、刪除**、重新開到工作台、用它開模擬面試，並匯出 **Word（.docx）**（PDF 透過瀏覽器列印）。
- **模擬面試**：依 JD 與你的履歷出題，逐題即時回饋與評分。可從任一份投遞包或貼 JD 開始；**每個職缺各自一個對話分頁**，可同時跑多場、互不覆蓋。
- **個人化**：跨 session 記住最近履歷（免重傳）與偏好（目標職稱／語氣／想強調技能），並套用到產出。

## LLM 後端

「免 AI 找職缺」不需要設定本節任何後端。要使用 AI 精準搜尋、履歷健檢、投遞文件或模擬面試時，再從**右上角控制台**選 AI 引擎——**本機 CLI 訂閱**（免 API key）、**本機模型**（Ollama / llama.cpp）或 **BYOK**（任何 OpenAI 相容端點）。選了即生效；「測試」只是選用的連線檢查、非門檻。本機 CLI 可**重新掃描**、並可**自選模型**：

| 後端         | 認證方式                          | 說明                                                                                  |
| ------------ | --------------------------------- | ------------------------------------------------------------------------------------- |
| `claude_cli` | Claude Code 訂閱                  | **預設。** 免 API key；會移除 `ANTHROPIC_*` 環境變數。模型可自選（預設自動分層）。     |
| `codex_cli`  | Codex 訂閱                        | 免 API key。模型可自選；預設沿用你的 Codex 設定。                                      |
| `ollama`     | 本機模型                          | 預設支援 Ollama；也可切到 llama.cpp server 或自訂本機 OpenAI-compatible endpoint。可重新偵測本機模型並以下拉選擇；品質與速度取決於本機硬體與模型。 |
| `openai`     | BYOK——任何 OpenAI 相容端點        | `base_url` + `api_key` + `model`。可接 OpenAI、DeepSeek、Gemini、Groq、OpenRouter、Ollama、LM Studio、vLLM…  |

CLI 後端會透過你機器上已登入的 CLI 呼叫對應 provider；本機模型與 BYOK 都走 OpenAI-compatible endpoint。完整 AI 功能只存在 local-first 桌面／自架模式，BYOK 與本機模型設定只寫進你本機的 `.env`；公開 Web 測試版不接受 AI key。另有 API key 後端（`anthropic`）供自架或 CI 使用。

## 隱私與資料

桌面版會在本機保存履歷記憶、偏好、搜尋紀錄、投遞包、`.env` 與錯誤紀錄。公開 Web 測試版不建立帳號或伺服器端履歷資料，但上傳內容會在該次請求中由伺服器解析，結果則留在該裝置瀏覽器。你可以在桌面版 **設定 → 清除個人資料** 清除本機資料；Web 版則清除該網站的瀏覽器資料。

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
- **漸進式產出**：Web 預設只執行解析、匹配與客製履歷；使用者勾選後才加入求職信、面試準備、公司情報或一次性 AI 品管。適配路由是本機門檻判斷，不另花一次 LLM 呼叫；正常 Profile 也不會在每個 agent 重複傳完整履歷原文。
- **自動找職缺**以 **Server-Sent Events** 邊搜、邊比對、邊串流回瀏覽器；免 AI 模式不初始化 LLM 後端，指定公司搜尋也只查求職網站、不執行 AI WebSearch。
- 應用層 SQLite 存放投遞包（含生命週期狀態：進行中 → 待審 → 已核可）、使用者記憶與搜尋紀錄；在「我的投遞包」核可。_（獨立的 CLI 仍保留可續跑、檔案型的人工核可關卡：`interrupt()` / `Command(resume=…)`。）_
- CLI 後端下模型自動分層：解析用 **haiku**、匹配／生成用 **sonnet**、選配 AI 品管用 **opus**（可於各後端覆寫）。

## 品質評測

專案保留 5 組職缺／履歷 golden set，可對完整文件跑**一次性 AI 品管**，量測通過率與平均分。免 AI 探索另有 40 組不含真實個資的合成職類履歷，涵蓋行政、零售、餐旅、物流、製造、營建、醫護、教育、法律、媒體與服務業，驗證「辨識職稱 → 搜尋詞 → 排序」不會只對工程師履歷成立。產品流程不會因評分未達標而自動重寫；使用者可先看具體建議，再決定是否修改，避免不可預期的等待時間與 token 消耗。

```bash
python -m app.evals.harness     # 對每個 golden 案例產出一次並品管，寫入 app/evals/results.json
```

歷史 A/B 結果的彙整函式仍有獨立單元測試；新的 harness 則直接輸出本次通過率與平均分。

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
  sources/    # 104 / Yourator / LinkedIn / Cake 搜尋 + registry + 縣市／遠端型態正規化
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
