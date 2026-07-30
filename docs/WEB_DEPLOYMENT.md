# 公開 Web 測試版部署

Jobsmith 的公開 Web 模式是給手機使用者試用的精簡入口，不是把桌面版直接公開：

- 只開放「履歷預覽、免 AI 找職缺、停止搜尋」相關 API。
- 強制使用確定性本機規則，不讀取 Claude Code、Codex、Ollama 或 BYOK 設定。
- 不初始化 Jobsmith 的 SQLite，不保存履歷、搜尋紀錄或投遞包。
- Profile 回傳前移除 `raw_text`；搜尋結果只留在使用者瀏覽器的 `localStorage`。
- 每個來源最多搜尋 2 頁、最多 2 間指定公司，並有工作階段限流、有界排隊與同時搜尋限制。
- 相同的公開職稱／地區／遠端條件會短期共用來源結果；快取鍵與內容不包含履歷、Profile 或配對分數。
- 可選擇啟用伺服器端匿名產品事件；預設關閉，桌面版不啟用，也不記錄履歷或搜尋內容。
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

目前 Blueprint 的單一實例容量保護設定如下：

| 環境變數 | 預設值 | 用途 |
|---|---:|---|
| `JOBSMITH_PUBLIC_PREVIEW_CONCURRENCY` | 2 | 同時解析的履歷預覽數 |
| `JOBSMITH_PUBLIC_SEARCH_CONCURRENCY` | 3 | 同時執行的搜尋數 |
| `JOBSMITH_PUBLIC_SEARCH_QUEUE` | 12 | 額外等待的搜尋數；超過才回覆稍後再試 |
| `JOBSMITH_PUBLIC_SEARCH_WAIT_SECONDS` | 90 | 單次最長排隊秒數 |
| `JOBSMITH_PUBLIC_SEARCH_CACHE_TTL` | 900 | 匿名職缺來源快取秒數 |
| `JOBSMITH_PUBLIC_SEARCH_CACHE_ENTRIES` | 64 | 最多保留的查詢條件組數 |
| `JOBSMITH_PUBLIC_ANALYTICS` | 0 | 設為 `1` 才嘗試送出匿名產品事件 |
| `JOBSMITH_POSTHOG_HOST` | `https://eu.i.posthog.com` | 只接受 PostHog EU 或 US ingestion host |
| `JOBSMITH_POSTHOG_PROJECT_KEY` | 未設定 | 只放 Render Environment，不可提交到 GitHub |

排隊採 FIFO；使用者會在原本的 SSE 連線中看到位置訊息，輪到時自動繼續，不需要重新送出。
限流依簽章瀏覽器工作階段計算，避免手機電信共用 IP 讓不同使用者互相占用額度。完全失敗的來源只會
短暫快取最多 60 秒，成功或部分成功的結果則使用上表 TTL。公開前端若已完成檔案預覽，開始搜尋時
只回傳精簡 Profile，不會再次上傳及解析完整履歷。

免費 Render Web Service 會在閒置後休眠，第一次打開可能要等待約一分鐘；檔案系統也是暫時的。
這正好符合目前不保存個資的預覽模式，但不適合承諾正式服務 SLA。若流量成長，應升級方案並把
職缺抓取進一步改成跨實例快取／排程同步；目前的記憶體佇列與快取會在重新部署、重啟或休眠後清空。

## 匿名流量與轉換分析

若要在宣傳後查看實際開啟量、手機占比、履歷辨識／搜尋完成率、排隊與快取狀態，可啟用選配的 PostHog server-side 分析。瀏覽器不載入 PostHog SDK；事件經固定欄位白名單後由 Jobsmith 伺服器送出，DNT／GPC 會被尊重，履歷、搜尋字詞、公司、URL、原始 cookie、完整 User-Agent 與訪客 IP 都不會被轉送。

建立免費專案、設定 Render 私密環境變數、建立看板與 Threads UTM 連結的完整步驟，請見[公開 Web 匿名使用分析](PRODUCT_ANALYTICS.md)。

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
8. 若有啟用匿名分析，確認 `/api/runtime` 回傳 `analytics_enabled: true`，且 PostHog Live events 只出現文件列出的固定事件與欄位。
