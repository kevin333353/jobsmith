# 公開 Web 測試版部署

Jobsmith 的公開 Web 模式是給手機使用者試用的精簡入口，不是把桌面版直接公開：

- 只開放「履歷預覽、免 AI 找職缺、停止搜尋」相關 API。
- 強制使用確定性本機規則，不讀取 Claude Code、Codex、Ollama 或 BYOK 設定。
- 不初始化 Jobsmith 的 SQLite，不保存履歷、搜尋紀錄或投遞包。
- Profile 回傳前移除 `raw_text`；搜尋結果只留在使用者瀏覽器的 `localStorage`。
- 每個來源最多搜尋 2 頁、最多 2 間指定公司，並有請求頻率與同時搜尋限制。
- 公開模式不提供投遞包、履歷健檢、面試、記憶或設定 API。

## 用 Render 建立測試站

Repo 根目錄已包含 `Dockerfile` 與 `render.yaml`。在 Render Dashboard 選 **New → Blueprint**，
連接這個 GitHub repo 後套用 Blueprint，即會建立新加坡區的 `jobsmith-web` Web Service。

Render 會自動提供 `RENDER_EXTERNAL_HOSTNAME`，Jobsmith 只接受該精確 Host 與 HTTPS Origin。
若之後綁定自訂網域，請把網域加到逗號分隔的 `JOBSMITH_PUBLIC_HOSTS` 環境變數，例如：

```text
jobs.example.com,www.jobs.example.com
```

健康檢查路徑是 `/api/healthz`。正式站的 session cookie 必須保持
`JOBSMITH_PUBLIC_COOKIE_SECURE=1`。

免費 Render Web Service 會在閒置後休眠，第一次打開可能要等待約一分鐘；檔案系統也是暫時的。
這正好符合目前不保存個資的預覽模式，但不適合承諾正式服務 SLA。若流量成長，應升級方案並把
職缺抓取改成受控快取／排程同步，避免每位訪客都即時查第三方網站。

## 本機模擬公開模式

PowerShell：

```powershell
$env:JOBSMITH_PUBLIC_WEB = "1"
$env:JOBSMITH_PUBLIC_COOKIE_SECURE = "0"
python -m uvicorn app.server:app --host 127.0.0.1 --port 8011
```

`JOBSMITH_PUBLIC_COOKIE_SECURE=0` 只供本機 HTTP 測試；公開 HTTPS 部署不可關閉。

Docker：

```bash
docker build -t jobsmith-web .
docker run --rm -p 10000:10000 -e JOBSMITH_PUBLIC_COOKIE_SECURE=0 jobsmith-web
```

然後開啟 <http://127.0.0.1:10000>。

## 上線前驗收

1. 手機以 HTTPS 開啟公開網址。
2. 上傳一份不含真實個資的合成 PDF、DOCX 或 TXT。
3. 確認可修改目標職稱、展開搜尋條件並開始搜尋。
4. 確認結果可在目前資料池即時篩選，且每張卡只提供「看原職缺」。
5. 重新整理後結果仍在，但履歷檔案與履歷原文不會被還原。
6. 確認 `/api/memory`、`/api/searches`、`/api/run` 都回 404。
7. 清除該網站的瀏覽器資料，確認本機搜尋結果消失。
