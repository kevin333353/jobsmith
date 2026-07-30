# 公開 Web 匿名使用分析

Jobsmith 公開 Web 可選擇把少量產品事件送到 PostHog Cloud，方便宣傳後查看流量、履歷辨識完成率、搜尋完成率與容量瓶頸。此功能預設關閉，只在公開 Web 模式且三個環境變數都正確時啟用；桌面版永遠不會送出這些事件。

PostHog 目前提供每月 100 萬筆事件的免費額度、單一免費專案與一年資料保留，建立時不需信用卡；實際方案仍以 [PostHog Pricing](https://posthog.com/pricing) 為準。

## 隱私設計

- 瀏覽器不載入 PostHog SDK，也不直接連線到 PostHog；所有事件由 Jobsmith 伺服器送出。
- 不使用 autocapture、session replay 或 PostHog cookie，也不建立 PostHog person profile。
- Jobsmith 不轉送訪客 IP、完整 User-Agent、Jobsmith session cookie、頁面 URL、referrer、履歷、姓名、聯絡方式、目標職稱、搜尋字詞、公司或職缺 URL。
- 同一瀏覽器只以「簽章 session + 日期」產生 HMAC 識別碼；識別碼每日更換，服務重新部署後也會更換，不能在長期或不同站點間追蹤。
- 只保留固定白名單中的低基數區間，例如 mobile／desktop、成功／失敗、耗時區間、結果數區間、是否排隊、快取狀態，以及手動設定的短 UTM campaign。
- `DNT: 1` 或 `Sec-GPC: 1` 的請求完全不記錄產品事件。
- PostHog payload 設定 `$process_person_profile=false` 與 `$geoip_disable=true`。Jobsmith 只讓 PostHog 看到 Render 伺服器送出事件的連線，不把訪客端 IP 加入 payload。

完整資料處理說明請見[隱私與資料處理](PRIVACY.md)。PostHog 也提供 [data collection controls](https://posthog.com/docs/privacy/data-collection) 說明。

## 在 Render 啟用

1. 建立 PostHog Cloud 專案；若 Jobsmith 部署在新加坡，可選 EU Cloud。
2. 在 PostHog 專案設定複製 **Project API key**，格式會是 `phc_...`。不要使用 Personal API key。
3. 到 Render 的 `jobsmith-web` → **Environment** 設定：

   | 環境變數 | 值 |
   |---|---|
   | `JOBSMITH_PUBLIC_ANALYTICS` | `1` |
   | `JOBSMITH_POSTHOG_HOST` | `https://eu.i.posthog.com`，若專案在 US 則用 `https://us.i.posthog.com` |
   | `JOBSMITH_POSTHOG_PROJECT_KEY` | PostHog 的 `phc_...` Project API key |

4. 儲存環境變數並讓 Render 重新部署／重啟服務。
5. 用瀏覽器先開啟網站、完成一次履歷預覽與搜尋。在瀏覽器 Network 面板查看 `/api/runtime`，`analytics_enabled` 應為 `true`。
6. 回到 PostHog 的 Live events，應看到 `jobsmith_web_web_opened`、`jobsmith_web_resume_preview_completed` 與 `jobsmith_web_search_completed`。

`render.yaml` 只宣告變數名稱與預設關閉狀態；Project API key 必須留在 Render Environment，不可寫入 GitHub、README、issue、log 或截圖。

## 建議看板

先建立以下 Insights，再放進同一個 Dashboard：

| 指標 | 事件／拆分 |
|---|---|
| 每日開啟量 | `jobsmith_web_web_opened`，按日計算事件數 |
| 每日匿名使用者 | `jobsmith_web_web_opened`，按日計算 unique users；識別碼每日輪替，因此只適合看「當日」而非長期回訪 |
| 使用漏斗 | `web_opened` → `resume_preview_completed` → `search_started` → `search_completed` |
| 履歷辨識失敗 | `resume_preview_failed`，依 `failure_category` 拆分 |
| 搜尋失敗 | `search_failed`，依 `failure_category` 拆分 |
| 手機占比 | `web_opened`，依 `device` 拆分 |
| 宣傳來源 | `web_opened`，依 `source` 與 `campaign` 拆分 |
| 搜尋效能 | `search_completed`，依 `duration_bucket` 拆分 |
| 容量與快取 | `queue_entered`、`queue_full`；`search_completed` 依 `cache_status` 拆分 |

Jobsmith 會送出的固定事件如下：

- `jobsmith_web_web_opened`
- `jobsmith_web_resume_preview_completed`
- `jobsmith_web_resume_preview_failed`
- `jobsmith_web_search_started`
- `jobsmith_web_queue_entered`
- `jobsmith_web_queue_full`
- `jobsmith_web_search_completed`
- `jobsmith_web_search_failed`

## Threads 宣傳連結

每篇貼文使用不同、無個資的短 campaign，即可比較成效：

```text
https://jobsmith-web.onrender.com/?utm_source=threads&utm_campaign=threads_202607_launch
```

`utm_source` 只接受 `threads`、`github`、`google`、`facebook`、`instagram` 或 `x`；其他值不會直接送出。`utm_campaign` 只接受 1–40 個英數、句點、底線或連字號，請勿放姓名、Email 或其他個資。

## 停用與故障行為

- 把 `JOBSMITH_PUBLIC_ANALYTICS` 改成 `0` 並重啟即可停用。
- 未設定 key、key 格式錯誤或 host 不在 EU／US 固定清單時，Jobsmith 會自動保持停用。
- 事件採有界記憶體佇列非同步送出；PostHog 失效、逾時或佇列已滿時直接丟棄事件，不會拖慢或中斷履歷辨識與職缺搜尋，也不會把 payload 寫進 Jobsmith error log。
