# 隱私與資料處理 / Privacy and Data Handling

Jobsmith 是 local-first 的桌面 / 網頁 app。它不提供 hosted backend，但會處理履歷、職缺與求職偏好等敏感資料；公開使用前，請先了解資料會存在哪裡、何時會送到你選擇的 AI 後端。

## 會留在本機的資料

App 會把下列資料存在你的電腦：

- 使用者明確儲存的候選人 Profile（履歷結構化資料）
- 個人化偏好
- 已儲存的職缺搜尋結果
- 已產生的投遞包
- BYOK 設定，本機 `.env` 檔
- 診斷錯誤紀錄，本機 `error.log`

Windows `.exe` 版本會盡量把 app data 寫在執行檔旁的 `JobsmithData/`。從原始碼啟動時，預設寫到 repo 的 `data/` 目錄，除非你用環境變數覆寫。

## 可能離開本機的資料

當你執行 AI 功能時，履歷、職缺描述、上下文與 prompt 會送到你選擇的 AI 後端：

- `claude_cli`：交給你本機已登入的 Claude Code CLI 處理
- `codex_cli`：交給你本機已登入的 Codex CLI 處理
- `ollama`：送到你設定的本機 OpenAI-compatible endpoint（預設 Ollama，也可用 llama.cpp server）
- `openai`：送到你設定的 OpenAI-compatible endpoint

Jobsmith 本身不營運雲端資料服務。如果本機模型 endpoint 指向 `127.0.0.1` / `localhost`，AI 請求會留在你的機器；如果你設定第三方 AI endpoint，該 provider 的資料政策會適用。

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

App 會把診斷錯誤寫到 `error.log`。請在 **設定 → 錯誤紀錄與回報** 查看位置。回報 issue 時，可以貼相關錯誤訊息，但請先移除 API key、履歷內容、電話、Email、公司內部資訊等敏感資料。

## 職缺來源

Jobsmith 會低頻查詢第三方網站的公開職缺頁面。搜尋結果可能因來源網站改版、封鎖或限流而不完整。使用者必須自行遵守各來源網站的服務條款與 robots policy。

## AI 生成內容

AI 產生的履歷、求職信、公司情報與面試回答可能有誤。送出給雇主前，請務必人工檢查與修正。
