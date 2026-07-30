# 隱私與資料處理 / Privacy and Data Handling

Jobsmith 以 local-first 桌面 app 為主，另有功能受限的公開 Web 測試版。兩者都會處理履歷、職缺與求職偏好等敏感資料；使用前請先確認自己進入的是本機桌面模式或公開 Web 模式，並了解資料流向。

## 會留在本機的資料

App 會把下列資料存在你的電腦：

- 使用者明確儲存的候選人 Profile（履歷結構化資料）
- 個人化偏好
- 已儲存的職缺搜尋結果
- 已產生的投遞包
- BYOK 設定，本機 `.env` 檔
- 診斷錯誤紀錄，本機 `error.log`

Windows `.exe` 版本會盡量把 app data 寫在執行檔旁的 `JobsmithData/`。從原始碼啟動時，預設寫到 repo 的 `data/` 目錄，除非你用環境變數覆寫。

## 公開 Web 測試版

公開 Web 模式不需帳號、不啟用 AI，也不初始化 Jobsmith 的 SQLite：

- 上傳的 PDF、DOCX 或 TXT 會送到 Jobsmith Web 伺服器，僅供該次履歷辨識與搜尋使用；應用程式不建立履歷、搜尋紀錄或投遞包資料列。HTTP multipart 處理期間可能使用程序記憶體或作業系統暫存空間，請勿將「不保存」誤解為「內容從未離開手機」。
- 回傳給瀏覽器的結構化 Profile 會移除履歷原文 `raw_text`。職缺結果與不含原文的 Profile 會存在該裝置瀏覽器的 `localStorage`，讓重新整理後不用重跑搜尋；清除網站資料即可刪除。
- 完整履歷不會送到 104、Cake、Yourator、LinkedIn 等職缺來源；這些來源只會收到目標職稱關鍵字與使用者選擇的地區／篩選條件。
- 公開站的雲端供應商仍會處理連線所需的 IP、時間與一般存取紀錄。Jobsmith 公開模式不主動把履歷內容寫入診斷錯誤檔。
- 公開模式封鎖記憶、搜尋紀錄、投遞包、履歷健檢、面試與 AI 後端設定 API，避免不同訪客共用桌面版資料。

目前公開站屬測試用途；請先用移除電話、Email、地址等欄位的履歷副本試用。若需要完整 AI 與長期保存功能，請使用本機桌面版。

## 可能離開本機的資料

預設的「免 AI 找職缺」會在 Jobsmith 本機程序解析履歷、產生搜尋前的目標職稱預覽並計算配對分數，不會探測或呼叫 AI 後端。使用者可在本機介面修正目標職稱。為了取得即時職缺，系統仍會把確認後的職稱關鍵字、地區與所選篩選條件送到 104、Cake、Yourator、LinkedIn 等職缺來源；不會把完整履歷送給這些職缺來源。

當你執行 AI 功能時，履歷、職缺描述、上下文與 prompt 會送到你選擇的 AI 後端：

- `claude_cli`：交給你本機已登入的 Claude Code CLI 處理
- `codex_cli`：交給你本機已登入的 Codex CLI 處理
- `ollama`：送到你設定的本機 OpenAI-compatible endpoint（預設 Ollama，也可用 llama.cpp server）
- `openai`：送到你設定的 OpenAI-compatible endpoint

桌面版不依賴 Jobsmith hosted backend。如果本機模型 endpoint 指向 `127.0.0.1` / `localhost`，AI 請求會留在你的機器；如果你設定第三方 AI endpoint，該 provider 的資料政策會適用。公開 Web 測試版則只提供免 AI 搜尋，不接受 AI key。

## 候選人 Profile

履歷解析完成後只會在目前 session 使用；要跨 session 免重傳，必須在 **個人化 → 候選人 Profile** 明確儲存。重新開啟 App 後，已儲存 Profile 也不會自動套用到產出，使用前需要手動選擇。

## 清除個人資料

在 app 內開啟 **個人化 → 清除個人資料**，會清除：

- 瀏覽器中的履歷 / 搜尋 / run 快取
- 已儲存的候選人 Profile 與偏好
- 已儲存的搜尋紀錄
- 已產生的投遞包歷史
- 記憶體中的 run snapshot

AI 後端設定會保留，避免每次清履歷資料後都要重填 API key。

## 錯誤紀錄

桌面 App 會把診斷錯誤寫到 `error.log`。請在 **設定 → 錯誤紀錄與回報** 查看位置。公開 Web 模式不寫入此檔。回報 issue 時，可以貼相關錯誤訊息，但請先移除 API key、履歷內容、電話、Email、公司內部資訊等敏感資料。

## 職缺來源

Jobsmith 會低頻查詢第三方網站的公開職缺頁面。搜尋結果可能因來源網站改版、封鎖或限流而不完整。使用者必須自行遵守各來源網站的服務條款與 robots policy。

## AI 生成內容

AI 產生的履歷、求職信、公司情報與面試回答可能有誤。送出給雇主前，請務必人工檢查與修正。
