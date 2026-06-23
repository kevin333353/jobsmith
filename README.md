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
