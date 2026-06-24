# M9 — Agent 工程深度 實作計畫

> 產品級升級第二里程碑（作品集訊號優先路線的核心：把「8 個 agent」從 prompt 包裝升級成
> 可量測、可觀測、有真正調度與收斂反思的 agent 系統——這是讓 owner 被 AI-agent 工程師
> 職缺錄取的關鍵）。承接 M8（feat/m8-foundation），全套基線 110 passed。

**Goal:** 讓多 agent 系統具備：真・LLM supervisor 動態調度、逐節點 token/成本/延遲 telemetry、
收斂式分文件反思、可證明反思有效的 eval harness、跨重啟持久化。

**驗收總則:** 全測試綠燈；前端 build 過；新增測試涵蓋每項；eval 能跑出反思前後分數。

## 任務

### T1 — 逐節點 Telemetry（token / 成本 / 延遲）
- 新增 `app/telemetry.py`：用 contextvar 收集每次 LLM 呼叫的 {input_tokens, output_tokens, cost_usd}（單人本機假設）。`start_run() / record_llm() / marker() / drain_since()`。
- `app/llm_cli.py` `_run_claude`：解析 claude -p envelope 的 `usage` 與 `total_cost_usd`（目前直接丟掉）→ `telemetry.record_llm(...)`。
- `app/graph.py` `_safe`：以 `time.perf_counter` 計每節點延遲 + `drain_since` 取該節點 token/成本 → 寫入 state `telemetry` 通道（`Annotated[list,operator.add]`）。
- `app/server.py` `_stream`：開頭 `telemetry.start_run()`；update 帶 telemetry → 發 `telemetry` SSE。
- 前端：PipelineView 累計並顯示「本次：N 次呼叫 · X tokens · $Y · Zs」總計列（每 agent 徽章留待 M10 視覺化）。
- 測試：record/drain 單元；_safe 產出 telemetry；server 發 telemetry 事件。

### T2 — 持久化（SqliteSaver，跨重啟不失憶）
- `app/graph.py`：`MemorySaver` → `langgraph.checkpoint.sqlite.SqliteSaver`（db 路徑 `data/checkpoints.sqlite`，可用 env 覆寫）；提供 `build_graph(checkpointer=None)` 讓測試可注入 MemorySaver。
- `requirements.txt`：加 `langgraph-checkpoint-sqlite`。
- 測試：同一 thread_id 用「新 graph 實例（同 db）」仍能 resume（模擬重啟）。

### T3 — 收斂式分文件反思
- `app/models.py`：`CritiqueReport` 的 `feedback: list[str]` → 改 `per_doc: dict[str, list[str]]`（鍵 resume/cover_letter/interview）+ 保留 `feedback` 為相容彙總（可由 per_doc 攤平）。
- `app/agents/critic.py`：prompt 產出 per_doc 回饋。
- `app/graph.py`：`_feedback` 改回傳該文件專屬回饋；revise 只重跑「未過」的生成節點（用 supervisor 的 docs_to_revise 或 per-doc 分數），不再無腦全部重跑；`MAX_REVISIONS` 提到 3。
- 測試：只有 resume 未過時，僅 resume_tailor 重跑（cover/interview 不動）。

### T4 — 真・LLM Supervisor（動態調度，兌現賣點）
- 新增 `app/agents/supervisor.py`：`SupervisorDecision{next_action: Literal['proceed','stop','revise','approve'], docs_to_revise: list[str], rationale: str}`，deep 分層。
- `app/graph.py`：新增 supervisor 節點取代 `route_after_match`／`route_after_critic` 的硬判斷；LLM 失敗或逾時 → fallback 回原門檻邏輯（保底）。supervisor 的 docs_to_revise 驅動 T3 的 targeted revise。
- 測試：mock supervisor 回 proceed/stop/revise；LLM 例外 → fallback 門檻；docs_to_revise 正確路由。

### T5 — Eval harness（用數字證明反思有效）
- 新增 `app/evals/`：3-5 組 golden `(ParsedJob, Profile)` fixture；`judge.py` 用 LLM-as-judge（沿用 critic 評分軸）對成品打分；`run_eval.py` 跑「反思關（MAX_REVISIONS=0）vs 開」比較 pass-rate / 平均分提升。
- 測試：harness 邏輯用 FakeLLM 單元測（judge 聚合、on/off 比較）；真實跑分用 `@pytest.mark.live`（預設 deselect）。
- 產出數字寫入 README（M11 收尾時）。

## 風險與相依
- supervisor / 反思互相依賴（docs_to_revise 驅動 targeted revise）→ T3 先於 T4 落、但 T4 整合。
- telemetry 僅對 claude_cli（live 預設）完整；anthropic/codex best-effort。
- 單人本機假設（contextvar telemetry、sqlite 單檔）符合使用者選擇（不做多人/雲端）。
