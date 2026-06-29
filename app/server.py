"""FastAPI：以 SSE 串流跑反思迴圈圖，並用 HTTP 處理 human-in-the-loop。"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from fastapi import Body, FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from app import __version__, settings, task_control
from app.agents.company_jobs import find_company_jobs
from app.agents.job_search import derive_queries, fallback_rank_jobs, rank_jobs
from app.agents.resume_eval import evaluate_resume, fallback_resume_assessment, structure_profile
from app.cli import load_profile
from app.graph import build_graph
from app.intake.resume_parser import extract_text
from app.models import Profile
from app.sources import regions
from app.sources.registry import linkedin_search_url, search_all
from app.sources.salary import filter_jobs_by_salary, monthly_salary_bounds
from app.store import db as _appdb
from app.store import history as _history
from app.store import memory as _memory
from app.store import resume_checks as _resume_checks
from app.store import searches as _searches

app = FastAPI(title="Jobsmith")

_appdb.init_db()  # 應用層 sqlite（歷史/記憶）
_history.mark_stale_running_failed()  # 啟動時把上次殘留的「進行中」收尾為 failed


def _new_run_graph():
    """每次背景產生用獨立的 graph + 記憶體 checkpointer，讓多個產生可安全平行
    （彼此不共用 sqlite 連線；批次模式不需跨程序持久化，故用 MemorySaver）。"""
    return build_graph(checkpointer=MemorySaver())

_ROOT = Path(__file__).parent.parent  # 專案根（app/ 的上一層）
_FRONTEND_DIST = _ROOT / "frontend" / "dist"  # Vite 建置產物（產品級前端）
if (_FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

_ERROR_LOG = _ROOT / "data" / "error.log"
_MAX_RESUME_UPLOAD_BYTES = 5 * 1024 * 1024


def _open_folder(path: Path) -> None:
    folder = path.resolve()
    if os.name == "nt":
        os.startfile(str(folder))  # type: ignore[attr-defined]
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(folder)])


def _read_resume_upload(file: UploadFile) -> bytes:
    data = file.file.read(_MAX_RESUME_UPLOAD_BYTES + 1)
    if len(data) > _MAX_RESUME_UPLOAD_BYTES:
        max_mb = _MAX_RESUME_UPLOAD_BYTES // (1024 * 1024)
        raise ValueError(f"resume file is too large (max {max_mb} MB)")
    return data


def _resume_text_from_request(file: UploadFile | None, resume_text: str) -> tuple[str, str | None]:
    if file is None:
        return resume_text, None
    try:
        data = _read_resume_upload(file)
        return extract_text(data, file.filename or "resume.txt"), None
    except ValueError as exc:
        return "", str(exc)
    except Exception as exc:  # noqa: BLE001
        return "", f"resume file could not be parsed: {_err_detail(exc)}"


def _profile_from_json(raw: str) -> tuple[Profile | None, str | None]:
    if not (raw or "").strip():
        return None, None
    try:
        data = json.loads(raw)
        profile = Profile(**data)
        if not (profile.name.strip() or profile.summary.strip()):
            return None, "已儲存 Profile 缺少姓名與定位摘要，請重新上傳履歷。"
        return profile, None
    except Exception as exc:  # noqa: BLE001
        return None, f"已儲存 Profile 格式無法讀取：{_err_detail(exc)}"


def _err_detail(exc: Exception) -> str:
    """回傳「類別: 訊息(截斷)」供前端顯示，並把完整 traceback 落地到 data/error.log（盡力而為）。

    視窗版 exe 沒有 console，否則錯誤細節會直接消失、無從診斷。只印類別名稱（如「RuntimeError」）
    無法分辨真正原因（CLI 找不到／rc≠0／回報錯誤／結構化解析失敗 是完全不同的問題）。
    """
    try:
        _ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} =====\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass  # 寫日誌失敗不可影響回應
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def serialize_update(update: dict) -> dict:
    """把 LangGraph 的 state 更新（可能含 Pydantic）轉成可 JSON 的 dict。"""
    out = {}
    for k, v in update.items():
        if isinstance(v, BaseModel):
            out[k] = v.model_dump()
        else:
            out[k] = v
    return out


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(
        obj,
        ensure_ascii=False,
        default=lambda o: o.model_dump() if isinstance(o, BaseModel) else str(o),
    ) + "\n\n"


def _stopped_sse(message: str = "已停止任務") -> str:
    return _sse({"type": "stopped", "message": message})


def _task_from_id(task_id: str = "") -> task_control.TaskToken:
    return task_control.create_task(task_id)


def _finish_task(token: task_control.TaskToken | None) -> None:
    if token is not None:
        task_control.finish_task(token.task_id)


# ---- 背景投遞包流程：產生投遞包改成射後不理的背景工作 ----
# 一按就在「我的投遞包」建紀錄、伺服器背景跑完；瀏覽器重新整理/返回/切分頁都不中斷。
# 多個產生可平行（每個用獨立 graph + 記憶體 checkpointer）；超過上限的排隊。
_MAX_PARALLEL_RUNS = 4
_RUN_EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_PARALLEL_RUNS, thread_name_prefix="pipeline")
_RUNS: dict[str, "_Run"] = {}
_RUNS_LOCK = threading.Lock()


class _Run:
    """單次背景產生的進度緩衝：事件序列 + 完成旗標，供前端輪詢（重新整理可從 0 重播）。"""

    def __init__(self, thread_id: str, package_id: int):
        self.thread_id = thread_id
        self.package_id = package_id
        self.events: list[dict] = []
        self.done = False
        self.cancel_requested = False
        self.future = None
        self._lock = threading.Lock()

    def emit(self, ev: dict) -> None:
        with self._lock:
            if self.cancel_requested and ev.get("type") not in {"stopped", "error"}:
                return
            self.events.append(ev)

    def finish(self) -> None:
        with self._lock:
            self.done = True

    def request_stop(self, message: str = "已停止任務") -> None:
        with self._lock:
            self.cancel_requested = True
            if not any(ev.get("type") == "stopped" for ev in self.events):
                self.events.append({"type": "stopped", "message": message})
            self.done = True

    def is_cancelled(self) -> bool:
        with self._lock:
            return self.cancel_requested

    def snapshot(self, since: int) -> tuple[list[dict], bool]:
        with self._lock:
            return self.events[since:], self.done


def _prune_runs() -> None:
    """避免長時間累積：超過 15 筆時丟掉較舊的已完成紀錄（之後輪詢會改從歷史載入）。"""
    if len(_RUNS) <= 15:
        return
    for k in [k for k, r in _RUNS.items() if r.done][:-5]:
        _RUNS.pop(k, None)


def _jd_title(jd_text: str) -> str:
    """從 JD 取第一行非空白當暫時標題（解析完成前先給使用者看得懂的名稱）。"""
    for line in (jd_text or "").splitlines():
        s = line.strip()
        if s:
            return s[:60]
    return "（產生中）"


def _run_pipeline_bg(run: "_Run", initial: dict, config: dict, graph) -> None:
    """背景執行緒跑整張 graph（每個產生用自己的 graph，可平行）：逐節點把事件寫進 run 緩衝，
    跑完更新歷史那筆為 done。"""
    try:
        for chunk in graph.stream(initial, config, stream_mode="updates"):
            if run.is_cancelled():
                _history.set_status(run.package_id, "stopped")
                return
            for node, update in chunk.items():
                if run.is_cancelled():
                    _history.set_status(run.package_id, "stopped")
                    return
                if node == "__interrupt__":
                    continue
                update = update or {}
                for err in update.get("errors") or []:
                    run.emit({"type": "node_error", "node": err.get("node", node),
                              "message": err.get("message", "")})
                for t in update.get("telemetry") or []:
                    run.emit({"type": "telemetry", **t})
                run.emit({"type": "node", "node": node, "data": serialize_update(update)})
        if run.is_cancelled():
            _history.set_status(run.package_id, "stopped")
            return
        snapshot = graph.get_state(config)
        final = serialize_update(snapshot.values)
        _history.update_package_result(run.package_id, final)
        run.emit({"type": "done", "package_id": run.package_id})
    except Exception as exc:  # noqa: BLE001 — 背景出錯也要收尾，不讓那筆永遠卡「進行中」
        if run.is_cancelled():
            _history.set_status(run.package_id, "stopped")
            return
        detail = _err_detail(exc)
        run.emit({"type": "error", "message": detail})
        try:
            _history.fail_package(run.package_id, detail)
        except Exception:
            pass
    finally:
        run.finish()


class RunBody(BaseModel):
    jd_text: str
    # 使用者真實履歷結構（由 /api/jobs/auto 或 /api/resume/evaluate 的 profile 事件帶入）。
    # 缺省時才退回 demo profile（CLI / 測試後備）。
    profile: dict | None = None
    # 個人化偏好（語氣/目標職稱/年資/想強調技能）；套進 profile 讓各生成 agent 採用。
    preferences: dict | None = None


# 注意：以下兩個串流端點用一般 def（非 async def），讓 Starlette 在 threadpool 執行
# 同步產生器，避免 claude_cli 的同步 subprocess 阻塞事件迴圈、卡住其他請求。
@app.post("/api/resume/evaluate")
def resume_evaluate(
    file: UploadFile | None = File(default=None),
    resume_text: str = Form(default=""),
    task_id: str = Form(default=""),
):
    resume_label = file.filename if file and file.filename else ("貼上文字" if resume_text.strip() else "")
    text, text_error = _resume_text_from_request(file, resume_text)
    token = _task_from_id(task_id)

    def gen():
        try:
            yield _sse({"type": "start", "task_id": token.task_id})
            token.check()
            if text_error:
                yield _sse({"type": "error", "message": text_error})
                return
            if not text.strip():
                yield _sse({"type": "error", "message": "請提供履歷檔案或文字"})
                return
            # 功能性把關：健檢同樣需要 AI，接不通就先擋下並引導登入（而非靜默備援健檢）。
            yield _sse({"type": "progress", "step": "backend", "message": "檢查 AI 引擎連線中…"})
            with task_control.task_context(token):
                live, live_msg = ensure_backend_live(settings.current_backend())
            if not live:
                yield _sse({"type": "error", "message": live_msg})
                return
            yield _sse({
                "type": "progress",
                "step": "received",
                "message": "已收到履歷，準備開始健檢；通常需要 30 秒到 2 分鐘。",
            })
            token.check()
            yield _sse({
                "type": "progress",
                "step": "structure",
                "message": "解析履歷背景中…正在整理姓名、定位、技能與經歷。",
            })
            with task_control.task_context(token):
                profile = structure_profile(text)
            token.check()
            # 含 raw_text 原文，供使用者接著到「投遞包工作台」手動開跑時帶入本人背景。
            yield _sse({"type": "profile", "data": profile.model_dump()})
            yield _sse({
                "type": "progress",
                "step": "evaluate",
                "message": "深度健檢評估中…會檢查 ATS、量化成果、台灣履歷慣例與改寫範例，長履歷或 CLI 模型可能需要更久。",
            })
            token.check()
            try:
                with task_control.task_context(token):
                    assessment = evaluate_resume(text, profile)
            except Exception as exc:  # noqa: BLE001 - resume health should degrade on AI/runtime failures
                if isinstance(exc, task_control.TaskCancelled):
                    raise
                yield _sse({
                    "type": "progress",
                    "step": "fallback",
                    "message": "AI 回覆格式不正確，正在改用保守備援健檢產出可讀報告。",
                })
                assessment = fallback_resume_assessment(text, profile, reason=str(exc))
            token.check()
            yield _sse({
                "type": "progress",
                "step": "finalize",
                "message": "整理健檢報告中…",
            })
            check_id = _resume_checks.save_check(
                label="",
                resume_label=resume_label,
                profile=profile.model_dump(),
                assessment=assessment.model_dump(),
            )
            yield _sse({"type": "saved_check", "id": check_id})
            yield _sse({"type": "assessment", "data": assessment.model_dump()})
            yield _sse({"type": "done"})
        except task_control.TaskCancelled:
            yield _stopped_sse()
        except Exception as exc:  # LLM 後端 429/額度/截斷等：回傳友善訊息而非中斷串流
            yield _sse({"type": "error",
                        "message": f"AI 服務暫時無法使用，請稍後再試。（{_err_detail(exc)}）"})
        finally:
            _finish_task(token)

    return StreamingResponse(gen(), media_type="text/event-stream")


_RANK_BATCH = 12  # 每批送 LLM 排序的職缺數（批小→首批更快出現）


def _rank_in_batches(
    profile,
    jobs,
    batch: int = _RANK_BATCH,
    workers: int = 4,
    token: task_control.TaskToken | None = None,
):
    """把職缺切批、並行送 rank_jobs，哪批先完成就先 yield（供 SSE 邊排邊推）。

    並行多個 CLI 子行程：總時間≈一批，且首批很快就回；單批失敗該批以未評分(0)回，不中斷。
    """
    chunks = [jobs[i:i + batch] for i in range(0, len(jobs), batch)]
    if not chunks:
        return
    def run_rank(chunk):
        with task_control.task_context(token):
            if token is not None:
                token.check()
            return rank_jobs(profile, chunk, None)

    with ThreadPoolExecutor(max_workers=min(workers, len(chunks))) as ex:
        futs = {ex.submit(run_rank, c): c for c in chunks}
        for fut in as_completed(futs):
            if token is not None:
                token.check()
            try:
                yield fut.result()
            except task_control.TaskCancelled:
                raise
            except Exception:  # noqa: BLE001 — 單批失敗不影響其他批
                yield fallback_rank_jobs(profile, futs[fut], top_k=None)


def _parse_companies(raw: str) -> list[str]:
    """把使用者填的公司名單字串（逗號/頓號/換行分隔）切成乾淨清單，去重保序。"""
    import re
    out: list[str] = []
    for part in re.split(r"[,，、\n]", raw or ""):
        name = part.strip()
        if name and name not in out:
            out.append(name)
    return out


@app.post("/api/jobs/auto")
def jobs_auto(
    file: UploadFile | None = File(default=None),
    resume_text: str = Form(default=""),
    profile_json: str = Form(default=""),
    companies: str = Form(default=""),
    pages: int = Form(default=2),
    region: str = Form(default=""),
    max_experience_years: float | None = Form(default=None),
    salary_unit: str = Form(default="monthly"),
    min_salary: float | None = Form(default=None),
    max_salary: float | None = Form(default=None),
    include_unknown_salary: bool = Form(default=True),
    task_id: str = Form(default=""),
):
    """履歷 → 自動找職缺：解析履歷 → 推導關鍵字 → 搜尋多站 →（選填）併入指定公司的開缺 → 依履歷排序。

    pages：每個來源抓幾頁（使用者可在前端調整，預設 2、夾在 1–5）。
    region：搜尋前選定的縣市（逗號串接 key）。對所有來源一致生效——104 於來源端用 area
            代碼篩選（涵蓋更全），其餘來源在結果端用 location 過濾，使用者看到的就是同一份地區結果。
    """
    pages = max(1, min(5, pages))
    max_experience_years = (
        None if max_experience_years is None else max(0.0, min(50.0, max_experience_years))
    )
    min_salary_monthly, max_salary_monthly = monthly_salary_bounds(
        min_salary,
        max_salary,
        salary_unit,
    )
    region_keys = regions.parse_keys(region)
    area = regions.area_codes(region_keys)
    text, text_error = _resume_text_from_request(file, resume_text)
    posted_profile, profile_error = (None, None) if text.strip() else _profile_from_json(profile_json)
    company_list = _parse_companies(companies)
    token = _task_from_id(task_id)

    def gen():
        try:
            yield _sse({"type": "start", "task_id": token.task_id})
            token.check()
            if text_error:
                yield _sse({"type": "error", "message": text_error})
                return
            if profile_error:
                yield _sse({"type": "error", "message": profile_error})
                return
            if not text.strip() and posted_profile is None:
                yield _sse({"type": "error", "message": "請提供履歷檔案或文字"})
                return
            # 功能性把關：AI 真的接得通才開始搜尋，否則中止並引導登入——
            # 不再讓「沒接通」靜默退到本機備援、把爛結果偽裝成 AI 解析。
            yield _sse({"type": "progress", "step": "backend", "message": "檢查 AI 引擎連線中…"})
            with task_control.task_context(token):
                live, live_msg = ensure_backend_live(settings.current_backend())
            if not live:
                yield _sse({"type": "error", "message": live_msg})
                return
            token.check()
            if text.strip():
                yield _sse({"type": "progress", "step": "structure", "message": "解析履歷中…"})
                with task_control.task_context(token):
                    profile = structure_profile(text)
            else:
                yield _sse({"type": "progress", "step": "profile", "message": "使用目前 Profile…"})
                profile = posted_profile
                assert profile is not None
            token.check()
            # 把使用者真實履歷（含 raw_text 原文）送給前端，供「產生投遞包」時整包帶入 pipeline，
            # 讓 match/resume/cover/interview agent 拿到逐字履歷（檔案上傳時前端沒有原文，必須由後端帶）。
            yield _sse({"type": "profile", "data": profile.model_dump()})
            with task_control.task_context(token):
                queries = derive_queries(profile)
            token.check()
            yield _sse({"type": "queries", "queries": queries})

            seen: set[str] = set()
            resume_jobs = []
            region_matched_count = 0
            for q in queries[:3]:
                token.check()
                yield _sse({"type": "progress", "step": "search", "message": f"搜尋「{q}」中…"})
                for res in search_all(q, limit=15, pages=pages, area=area):
                    token.check()
                    # 104 已於來源端用 area 篩過；其餘來源在結果端依 location 過濾，地區一致生效。
                    region_kept = [j for j in res.jobs
                                   if res.source == "104" or regions.match_location(j.location, region_keys)]
                    region_matched_count += len(region_kept)
                    kept = _filter_jobs_by_experience(region_kept, max_experience_years)
                    kept = filter_jobs_by_salary(
                        kept,
                        min_monthly=min_salary_monthly,
                        max_monthly=max_salary_monthly,
                        include_unknown=include_unknown_salary,
                    )
                    yield _sse({"type": "source", "source": res.source,
                                "count": len(kept), "blocked": res.blocked})
                    for j in kept:
                        key = j.url or (j.title + j.company)
                        if key in seen:
                            continue
                        seen.add(key)
                        resume_jobs.append(j)

            # 誠實降級：AI 搜尋零結果 → 告知並改用後備樣本職缺，demo 永遠有東西看。
            used_fallback = False
            if not resume_jobs and region_matched_count == 0:
                used_fallback = True
                yield _sse({"type": "all_blocked",
                            "message": "即時職缺來源暫時取得不到結果，以下改用範例職缺示意，"
                                       "並請改用下方 LinkedIn / 104 直連搜尋。"})
                resume_jobs = _load_fallback_jobs()

            # ① AI 依履歷找到的職缺：分批『並行』排序、逐批串流給前端（邊收邊排序/篩選），
            # 不必等全部跑完；批次以穩定鍵排序，讓同一輸入分批一致。
            resume_jobs.sort(key=lambda j: j.url or (j.title + j.company))
            yield _sse({"type": "rank_start", "total": len(resume_jobs), "fallback": used_fallback})
            matches = []
            for batch in _rank_in_batches(profile, resume_jobs, token=token):
                token.check()
                matches.extend(batch)
                yield _sse({"type": "ranked_batch", "data": [m.model_dump() for m in batch]})
            li_loc = f"{region_keys[0]}, Taiwan" if region_keys else "Taiwan"
            yield _sse({"type": "linkedin",
                        "url": linkedin_search_url(queries[0] if queries else "", li_loc)})

            # ② 使用者指定的公司開缺：與 AI 搜尋『分開』收集、分開排序、分開顯示，
            # 避免低適配的公司職缺佔據 AI 推薦名單前段、又吃掉排序名額。
            company_pool = []
            for company in company_list:
                token.check()
                yield _sse({"type": "progress", "step": "company",
                            "message": f"查「{company}」的開缺中…"})
                try:
                    found = find_company_jobs(company, profile)
                except Exception:
                    found = []
                found = _filter_jobs_by_experience(found, max_experience_years)
                found = filter_jobs_by_salary(
                    found,
                    min_monthly=min_salary_monthly,
                    max_monthly=max_salary_monthly,
                    include_unknown=include_unknown_salary,
                )
                added = 0
                for j in found:
                    key = j.url or (j.title + j.company)
                    if key in seen:  # 已出現在 AI 結果就不重複列
                        continue
                    seen.add(key)
                    company_pool.append(j)
                    added += 1
                yield _sse({"type": "source", "source": company,
                            "count": added, "blocked": added == 0})
            if company_pool:
                yield _sse({"type": "progress", "step": "rank",
                            "message": f"依履歷排序 {len(company_pool)} 筆指定公司職缺…"})
                token.check()
                with task_control.task_context(token):
                    cmatches = rank_jobs(profile, company_pool, top_k=None)
                token.check()
                yield _sse({"type": "company_jobs",
                            "data": [m.model_dump() for m in cmatches]})
            yield _sse({"type": "done"})
        except task_control.TaskCancelled:
            yield _stopped_sse()
        except Exception as exc:  # LLM/網路錯誤：友善降級
            yield _sse({"type": "error",
                        "message": f"AI 服務暫時無法使用，請稍後再試。（{_err_detail(exc)}）"})
        finally:
            _finish_task(token)

    return StreamingResponse(gen(), media_type="text/event-stream")


def _filter_jobs_by_experience(jobs: list, max_years: float | None) -> list:
    if max_years is None:
        return jobs
    return [j for j in jobs if j.min_years is None or j.min_years <= max_years]


def _load_fallback_jobs() -> list:
    """來源全失敗時的後備樣本職缺（讓 demo/離線時仍有可排序內容）。"""
    from app.models import JobPosting
    path = _ROOT / "data" / "fallback_jobs.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [JobPosting(**j) for j in raw]
    except Exception:
        return []


@app.get("/api/sample")
def sample():
    jd = (_ROOT / "data" / "demo_jobs" / "ai_engineer.txt").read_text(encoding="utf-8")
    return {"jd_text": jd}


class JDFetchBody(BaseModel):
    url: str


@app.post("/api/jd/fetch")
def jd_fetch_endpoint(body: JDFetchBody):
    """貼職缺網址 → 抽取 JD 文字（104 走官方 content API，其餘走通用 HTML 抽取）。"""
    from app.intake.jd_fetch import JDFetchError, fetch_jd
    try:
        res = fetch_jd(body.url)
    except JDFetchError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception:
        return JSONResponse({"error": "抓取失敗，請改貼 JD 文字。"}, status_code=400)
    return {"title": res.title, "company": res.company, "text": res.text, "source": res.source}


_DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@app.post("/api/export/docx")
def export_docx(pkg: dict = Body(...)):
    """把（可能已編輯的）投遞包轉成 Word 檔下載。"""
    from app.export.docx_export import build_docx
    try:
        data = build_docx(pkg or {})
    except Exception:
        return JSONResponse({"error": "匯出失敗，請重試。"}, status_code=400)
    return Response(
        content=data, media_type=_DOCX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="job-package.docx"'},
    )


def _backend_available(name: str) -> bool:
    """偵測該後端是否可用：CLI 看執行檔；local/BYOK 看必要設定；anthropic 看金鑰。"""
    from app.llm_cli import _find_cli  # 與實際呼叫共用同一套尋找邏輯（含常見安裝路徑）
    if name == "claude_cli":
        return bool(_find_cli("claude", "CLAUDE_CLI_PATH"))
    if name == "codex_cli":
        return bool(_find_cli("codex", "CODEX_CLI_PATH"))
    if name == "ollama":
        return bool(settings.local_model_base_url() and settings.local_model_model())
    if name == "openai":  # 有金鑰，或有 base_url（如 Ollama / LM Studio 本機免金鑰）即可
        return bool(settings.byok_api_key() or settings.byok_base_url())
    if name == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return False


def _cli_version(name: str) -> str:
    """跑 `<cli> --version` 取版本字串（給設定面板的卡片顯示）；找不到/失敗回空字串。"""
    import subprocess

    from app.llm_cli import _find_cli
    spec = {"claude_cli": ("CLAUDE_CLI_PATH", "claude"),
            "codex_cli": ("CODEX_CLI_PATH", "codex")}.get(name)
    if not spec:
        return ""
    exe = _find_cli(spec[1], spec[0])
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=8,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        lines = (r.stdout or r.stderr or "").strip().splitlines()
        return lines[0][:80] if lines else ""
    except Exception:
        return ""


def _backend_option(b: str) -> dict:
    kind = settings.BACKEND_KIND.get(b, "api")
    opt = {"id": b, "label": settings.BACKEND_LABELS.get(b, b),
           "available": _backend_available(b), "kind": kind}
    if kind == "cli":
        opt["version"] = _cli_version(b)
    return opt


@app.get("/api/backend")
def get_backend():
    """目前作用中的 LLM 後端、可選清單（含 CLI 版本）、各 CLI 模型選項、BYOK 設定狀態。"""
    return {
        "current": settings.current_backend(),
        "options": [_backend_option(b) for b in settings.SUPPORTED_BACKENDS],
        "cli_models": {
            b: {"choices": settings.CLI_MODEL_CHOICES[b], "current": settings.cli_model(b)}
            for b in settings.CLI_MODEL_CHOICES
        },
        "byok": settings.byok_public(),
        "local_models": settings.local_model_public(),
    }


class BackendBody(BaseModel):
    backend: str
    task_id: str = ""


@app.post("/api/backend")
def post_backend(body: BackendBody):
    """切換 LLM 後端（執行期，單人本機）。選了即生效，不以測試結果為門檻。"""
    try:
        settings.set_backend(body.backend, persist=True)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    mark_backend_unverified(body.backend)  # 換後端 → 下次搜尋重新功能性探測
    return {"current": settings.current_backend()}


class CliModelBody(BaseModel):
    backend: str
    model: str


@app.post("/api/backend/model")
def post_backend_model(body: CliModelBody):
    """設定某本機 CLI 後端的模型策略；目前只允許 'auto'，避免列出未偵測的假模型。"""
    try:
        settings.set_cli_model(body.backend, body.model)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    mark_backend_unverified(body.backend)  # 換模型 → 下次搜尋重新功能性探測
    return {"backend": body.backend, "model": settings.cli_model(body.backend)}


class ByokBody(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@app.post("/api/backend/byok")
def post_backend_byok(body: ByokBody):
    """儲存 BYOK（OpenAI 相容）設定並寫回 .env；api_key 留空則保留既有金鑰。"""
    try:
        settings.set_byok(body.base_url, body.api_key, body.model)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    mark_backend_unverified("openai")  # 改 BYOK 設定 → 下次搜尋重新功能性探測
    return {"byok": settings.byok_public()}


class LocalModelBody(BaseModel):
    provider: str = "ollama"
    base_url: str = ""
    api_key: str = ""
    model: str = ""


def _local_model_base_url(provider: str, base_url: str) -> str:
    return (base_url or settings.LOCAL_MODEL_DEFAULT_BASE_URLS.get(provider, "")).strip().rstrip("/")


def _ollama_tags_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    return f"{base}/api/tags"


def _openai_models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def _dedupe_model_names(names: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        out.append(name)
        seen.add(name)
    return out


def _models_from_ollama_tags(data: dict) -> list[str]:
    rows = data.get("models") or []
    return _dedupe_model_names([
        str(row.get("name") or row.get("model") or "")
        for row in rows if isinstance(row, dict)
    ])


def _models_from_openai_list(data: dict) -> list[str]:
    rows = data.get("data") or []
    return _dedupe_model_names([
        str(row.get("id") or row.get("name") or row.get("model") or "")
        for row in rows if isinstance(row, dict)
    ])


def _detect_local_model_names(provider: str, base_url: str, api_key: str = "") -> list[str]:
    if provider not in settings.LOCAL_MODEL_PROVIDERS:
        raise ValueError(f"不支援的本機模型來源：{provider}")
    if not base_url:
        raise ValueError("請先填寫本機模型 Base URL。")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if provider == "ollama":
        r = requests.get(_ollama_tags_url(base_url), timeout=6, headers=headers)
        if not r.ok:
            raise RuntimeError(f"Ollama 回應 HTTP {r.status_code}")
        return _models_from_ollama_tags(r.json())
    r = requests.get(_openai_models_url(base_url), timeout=6, headers=headers)
    if not r.ok:
        raise RuntimeError(f"本機模型服務回應 HTTP {r.status_code}")
    return _models_from_openai_list(r.json())


@app.post("/api/backend/local-models")
def post_backend_local_models(body: LocalModelBody):
    """偵測本機模型清單；不儲存設定，也不切換目前後端。"""
    provider = (body.provider or "ollama").strip() or "ollama"
    base_url = _local_model_base_url(provider, body.base_url)
    api_key = body.api_key.strip()
    try:
        models = _detect_local_model_names(provider, base_url, api_key)
    except Exception as e:  # noqa: BLE001 — 偵測失敗要回 UI 友善訊息
        return {"ok": False, "models": [], "message": f"偵測失敗：{_err_detail(e)}"}
    if not models:
        return {"ok": False, "models": [], "message": "沒有偵測到本機模型，請確認服務已啟動且模型已安裝。"}
    return {"ok": True, "models": models, "message": f"偵測到 {len(models)} 個本機模型"}


@app.post("/api/backend/local-model")
def post_backend_local_model(body: LocalModelBody):
    """儲存本機模型設定；Ollama/llama.cpp 皆走 OpenAI-compatible endpoint。"""
    try:
        settings.set_local_model(
            provider=body.provider,
            base_url=body.base_url,
            api_key=body.api_key,
            model=body.model,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    mark_backend_unverified("ollama")
    return {"local_models": settings.local_model_public()}


# 連線測試：用最輕的模型（haiku）+ 最短提示，只求拿到任何回覆，盡快完成。
_PROBE_PROMPT = "只輸出數字 1"
_PROBE_TIMEOUT = 45


def _probe_claude() -> str:
    from app.llm_cli import _run_claude
    return _run_claude(_PROBE_PROMPT, "haiku", timeout=_PROBE_TIMEOUT)


def _probe_codex() -> str:
    from app.llm_cli import _run_codex
    # 沿用使用者設定的 codex 模型（不硬指定可能不存在的模型名），但把推理強度壓到 low，
    # 讓這個極短探測盡快完成；未知 config 鍵不會報錯（除非 --strict-config）。
    return _run_codex(_PROBE_PROMPT, timeout=_PROBE_TIMEOUT,
                      extra_args=["-c", 'model_reasoning_effort="low"'])


def _probe_openai() -> str:
    """用目前 BYOK 設定（base_url + key + model）跑一次極短呼叫。"""
    from langchain_openai import ChatOpenAI
    kwargs = {"model": settings.byok_model() or "gpt-4o-mini",
              "max_tokens": 50, "max_retries": 1, "timeout": _PROBE_TIMEOUT}
    if settings.byok_base_url():
        kwargs["base_url"] = settings.byok_base_url()
    if settings.byok_api_key():
        kwargs["api_key"] = settings.byok_api_key()
    return ChatOpenAI(**kwargs).invoke([("human", _PROBE_PROMPT)]).content


def _probe_local_model() -> str:
    """用目前本機模型設定跑一次極短呼叫。"""
    from langchain_openai import ChatOpenAI
    kwargs = {
        "model": settings.local_model_model() or "qwen3:8b",
        "base_url": settings.local_model_base_url(),
        "api_key": settings.local_model_api_key(),
        "max_tokens": 50,
        "max_retries": 1,
        "timeout": _PROBE_TIMEOUT,
    }
    return ChatOpenAI(**kwargs).invoke([("human", _PROBE_PROMPT)]).content


def _probe_backend(name: str) -> str:
    """真的對指定後端跑一次極短呼叫，回傳模型輸出字串（失敗則拋例外）。"""
    if name == "claude_cli":
        return _probe_claude()
    if name == "codex_cli":
        return _probe_codex()
    if name == "ollama":
        return _probe_local_model()
    if name == "openai":
        return _probe_openai()
    # anthropic
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=settings.get_model("cheap"), max_tokens=50).invoke(
        [("human", "只回覆兩個字：你好")]).content


# ── 功能性把關 ───────────────────────────────────────────────────────────
# 搜尋/健檢前「真的呼叫一次」後端確認接得通，而非只看 CLI 在不在——否則使用者
# 沒登入 AI 也能照搜、靜默退到本機備援、拿到偽裝成真的爛結果。通過會快取一小段
# 時間，避免每次搜尋都多花一次探測；切換後端/模型時失效（見 mark_backend_unverified）。
_PROBE_OK_TTL = 600.0  # 秒
_backend_live_at: dict[str, float] = {}


def _backend_signature(name: str) -> str:
    """後端 + 影響連線的設定（模型/端點）組成快取鍵；任一改變就重新探測。"""
    if name in ("claude_cli", "codex_cli"):
        return f"{name}:{settings.cli_model(name)}"
    if name == "ollama":
        return (
            f"ollama:{settings.local_model_provider()}|"
            f"{settings.local_model_base_url()}|{settings.local_model_model()}"
        )
    if name == "openai":
        return f"openai:{settings.byok_base_url()}|{settings.byok_model()}"
    return name


def mark_backend_verified(name: str) -> None:
    """記下「此後端剛剛實測接得通」，讓接下來的搜尋免去重複探測。"""
    _backend_live_at[_backend_signature(name)] = time.monotonic()


def mark_backend_unverified(name: str | None = None) -> None:
    """讓功能性把關的快取失效（切換後端/模型/BYOK 時呼叫），下次搜尋會重新探測。"""
    if name is None:
        _backend_live_at.clear()
    else:
        _backend_live_at.pop(_backend_signature(name), None)


def _probe_failure_message(name: str) -> str:
    if name == "claude_cli":
        return ("Claude Code 接不通——多半是還沒登入。請先在終端機執行 `claude` 完成登入，"
                "或到右上角控制台按「測試」確認連線後，再開始搜尋。")
    if name == "codex_cli":
        return ("Codex CLI 接不通——多半是還沒登入。請先在終端機執行 `codex` 完成登入，"
                "或到右上角控制台按「測試」確認連線後，再開始搜尋。")
    if name == "ollama":
        return ("本機模型接不通，請確認 Ollama 或 llama.cpp server 已啟動、base URL 正確，"
                "並且模型名稱已安裝/載入。")
    return ("AI 後端接不通，請到右上角控制台確認 base_url / api_key / model 設定，"
            "並按「測試」連線成功後再搜尋。")


def _backend_missing_message(name: str) -> str:
    if name == "ollama":
        return "請先設定本機模型名稱，並確認 Ollama/llama.cpp 服務已啟動。"
    return "找不到對應的 CLI 或金鑰，請先到右上角控制台選擇並安裝/登入 AI 引擎。"


def ensure_backend_live(name: str) -> tuple[bool, str]:
    """功能性把關：回 (是否接得通, 失敗時的引導訊息)。

    先看後端有沒有（CLI 執行檔／金鑰），再真的呼叫一次確認接得通。通過會快取
    _PROBE_OK_TTL 秒。任何 CLI／網路／驗證錯誤都當成「沒接通」，回引導訊息讓上層擋下搜尋。
    """
    if not _backend_available(name):
        return False, _backend_missing_message(name)
    sig = _backend_signature(name)
    last = _backend_live_at.get(sig)
    if last is not None and (time.monotonic() - last) < _PROBE_OK_TTL:
        return True, ""
    try:
        out = _probe_backend(name)
    except task_control.TaskCancelled:
        raise
    except Exception:  # noqa: BLE001 — 任何 CLI/網路/驗證錯誤都視為「沒接通」
        return False, _probe_failure_message(name)
    if not (out or "").strip():
        return False, _probe_failure_message(name)
    _backend_live_at[sig] = time.monotonic()
    return True, ""


@app.post("/api/backend/test")
def test_backend(body: BackendBody):
    """實測指定後端是否能連線（真的跑一次極短的 CLI 呼叫），供開場引導畫面顯示連線狀態。

    不改動目前作用中的後端——測試與切換分開，測失敗不會把使用者切到壞掉的後端。
    """
    name = body.backend
    if name not in settings.SUPPORTED_BACKENDS:
        return JSONResponse({"ok": False, "message": "不支援的後端"}, status_code=400)
    if not _backend_available(name):
        return {"ok": False, "message": _backend_missing_message(name)}
    token = _task_from_id(body.task_id) if body.task_id else None
    try:
        with task_control.task_context(token):
            task_control.check_cancelled()
            out = _probe_backend(name)
        ok = bool((out or "").strip())
        if ok:
            mark_backend_verified(name)  # 測試通過 → 之後搜尋免去重複探測
        return {"ok": ok, "message": "連線成功" if ok else "回覆為空，請重試。"}
    except task_control.TaskCancelled:
        return {"ok": False, "message": "已停止任務"}
    except Exception as e:  # noqa: BLE001 — 任何 CLI/網路錯誤都回友善訊息
        return {"ok": False, "message": f"連線失敗（{type(e).__name__}），請確認 CLI 已登入。"}
    finally:
        _finish_task(token)


# ── 更新檢查 ─────────────────────────────────────────────────────────────
# 與右上角 star 同一管道：只連 GitHub 公開 API、不送任何使用者資料。比對目前版本與最新
# release，新版才回 update_available=True，由前端跳「可更新」橫幅。
# 注意：這只幫得到「已含本檢查的版本」；更早、沒有這段的舊 exe 無法事後被通知。
_REPO = "kevin333353/jobsmith"
_RELEASES_API = f"https://api.github.com/repos/{_REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{_REPO}/releases/latest"


def _parse_version(text: str) -> tuple[int, ...]:
    """'v0.2.0' / '0.2.0-beta.1' → (0, 2, 0)，可直接比大小；解析不出回 ()。"""
    m = re.match(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", (text or "").strip())
    if not m:
        return ()
    return tuple(int(g) if g else 0 for g in m.groups())


def check_for_update(timeout: float = 4.0) -> dict:
    """查 GitHub 最新 release 並與目前版本比對。

    Best-effort：離線／限流／逾時／無 release 一律回 update_available=False，永不拋例外、
    永不影響 app。回傳 {current, latest, update_available, url}。
    """
    result = {"current": __version__, "latest": None,
              "update_available": False, "url": _RELEASES_PAGE}
    try:
        r = requests.get(_RELEASES_API, timeout=timeout,
                         headers={"Accept": "application/vnd.github+json",
                                  "User-Agent": f"jobsmith/{__version__}"})
        if not r.ok:
            return result
        data = r.json()
        tag = (data.get("tag_name") or "").strip()
        if not tag:
            return result
        result["latest"] = tag
        if data.get("html_url"):
            result["url"] = data["html_url"]
        cur, latest = _parse_version(__version__), _parse_version(tag)
        result["update_available"] = bool(cur and latest and latest > cur)
    except Exception:  # noqa: BLE001 — 更新檢查永不可影響 app
        pass
    return result


@app.get("/api/update-check")
def update_check():
    """前端啟動時呼叫：回目前版本與 GitHub 最新 release 的比對結果。"""
    return check_for_update()


class InterviewStartBody(BaseModel):
    jd_text: str
    profile: dict | None = None
    n: int = 6
    task_id: str = ""


class InterviewAnswerBody(BaseModel):
    jd_text: str
    question: str
    answer: str
    profile: dict | None = None
    task_id: str = ""


class InterviewSummaryBody(BaseModel):
    jd_text: str
    transcript: list[dict]
    task_id: str = ""


@app.post("/api/interview/start")
def interview_start(body: InterviewStartBody):
    from app.agents.interview_sim import generate_questions
    token = _task_from_id(body.task_id) if body.task_id else None
    try:
        with task_control.task_context(token):
            profile = _resolve_profile(body)
            task_control.check_cancelled()
            qs = generate_questions(body.jd_text, profile, n=body.n)
    except task_control.TaskCancelled:
        return JSONResponse({"error": "已停止任務"}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{_err_detail(exc)}）"},
                            status_code=400)
    finally:
        _finish_task(token)
    return {"questions": [q.model_dump() for q in qs]}


@app.post("/api/interview/answer")
def interview_answer(body: InterviewAnswerBody):
    from app.agents.interview_sim import evaluate_answer
    token = _task_from_id(body.task_id) if body.task_id else None
    try:
        with task_control.task_context(token):
            profile = _resolve_profile(body)
            task_control.check_cancelled()
            fb = evaluate_answer(body.question, body.answer, body.jd_text, profile)
    except task_control.TaskCancelled:
        return JSONResponse({"error": "已停止任務"}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{_err_detail(exc)}）"},
                            status_code=400)
    finally:
        _finish_task(token)
    return fb.model_dump()


class PipelineChatBody(BaseModel):
    doc_type: str = "resume"          # resume | cover
    current: str = ""                 # 目前文件內容（供上下文）
    jd_text: str = ""
    profile: dict | None = None
    messages: list[dict] = []          # [{role: user|assistant, content}]
    task_id: str = ""


@app.post("/api/pipeline/chat")
def pipeline_chat(body: PipelineChatBody):
    """履歷／求職信的多輪對話修改：回覆建議，並（必要時）回傳修訂後的文件欄位。"""
    from app.agents.refine import refine_document
    token = _task_from_id(body.task_id) if body.task_id else None
    try:
        with task_control.task_context(token):
            profile = _resolve_profile(body)
            task_control.check_cancelled()
            res = refine_document(body.doc_type, body.current, body.messages, body.jd_text, profile)
    except task_control.TaskCancelled:
        return JSONResponse({"error": "已停止任務"}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{_err_detail(exc)}）"},
                            status_code=400)
    finally:
        _finish_task(token)
    if body.doc_type == "resume":
        updated = (None if res.updated_summary is None and res.updated_bullets is None
                   else {"summary": res.updated_summary or "", "bullets": res.updated_bullets or []})
    else:
        updated = (None if res.updated_subject is None and res.updated_body is None
                   else {"subject": res.updated_subject or "", "body": res.updated_body or ""})
    return {"reply": res.reply, "updated": updated}


@app.post("/api/interview/summary")
def interview_summary(body: InterviewSummaryBody):
    from app.agents.interview_sim import summarize
    token = _task_from_id(body.task_id) if body.task_id else None
    try:
        with task_control.task_context(token):
            task_control.check_cancelled()
            s = summarize(body.jd_text, body.transcript)
    except task_control.TaskCancelled:
        return JSONResponse({"error": "已停止任務"}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{_err_detail(exc)}）"},
                            status_code=400)
    finally:
        _finish_task(token)
    return s.model_dump()


def _resolve_profile(body: RunBody) -> Profile:
    """優先用使用者真實履歷；缺省才退回 demo profile。"""
    if body.profile:
        data = dict(body.profile)
        p = Profile(**data)
        # Profile 已放寬以容忍模型輸出（name/summary 可空）；但若前端傳來的 profile 連
        # 姓名與定位都沒有，視為不可用 → 回 400 友善訊息，而非拿空殼去跑 pipeline。
        if not (p.name.strip() or p.summary.strip()):
            raise ValueError("履歷缺少姓名與定位，無法產生投遞包，請重新上傳履歷。")
        return p
    return load_profile(str(_ROOT / "data" / "demo_profile.json"))


def _apply_preferences(profile: Profile, prefs: dict | None) -> Profile:
    """把個人化偏好套進 profile（summary 加註 + preferred_roles），讓各生成 agent 採用，
    不需更動 agent 簽名。prefs 缺省則原樣回傳。"""
    if not prefs:
        return profile
    titles = [t for t in (prefs.get("target_titles") or []) if str(t).strip()]
    if titles:
        profile.preferred_roles = list(dict.fromkeys([*profile.preferred_roles, *titles]))
    notes = []
    if prefs.get("tone"):
        notes.append(f"語氣偏好：{prefs['tone']}")
    if prefs.get("seniority"):
        notes.append(f"目標層級/年資：{prefs['seniority']}")
    emph = [s for s in (prefs.get("emphasize_skills") or []) if str(s).strip()]
    if emph:
        notes.append("想強調的技能：" + "、".join(emph))
    if notes:
        profile.summary = (profile.summary + "\n（個人化偏好——" + "；".join(notes) + "）").strip()
    return profile


@app.post("/api/run")
def run(body: RunBody):
    """產生投遞包（背景、射後不理）：立刻在『我的投遞包』建一筆進行中並回傳 thread_id/package_id；
    pipeline 在伺服器背景跑完（瀏覽器重新整理/返回/切分頁都不中斷），前端用 /api/run/events 輪詢進度。
    """
    # 履歷壞/缺 → 回 400 友善訊息（不建立進行中紀錄）。
    try:
        profile = _resolve_profile(body)
        profile = _apply_preferences(profile, body.preferences)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"error": f"履歷資料無法使用，請重新上傳履歷再試。（{_err_detail(exc)}）"},
            status_code=400)

    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    pid = _history.create_running_package(
        thread_id, body.jd_text, _jd_title(body.jd_text), profile.model_dump())
    initial = {
        "jd_text": body.jd_text, "profile": profile,
        "parsed_job": None, "match_report": None, "supervisor_decision": None,
        "company_brief": None, "tailored_resume": None, "cover_letter": None,
        "interview_kit": None, "critique": None, "revision_count": 0,
        # batch=True：背景跑、略過互動核可關卡（核可改到「我的投遞包」做）。
        "approved": None, "batch": True, "errors": [], "telemetry": [],
    }
    run_obj = _Run(thread_id, pid)
    # 沒帶真實履歷 → 用範例 demo，明確提醒使用者（避免把假人投遞包當成自己的）。
    if not body.profile:
        run_obj.emit({"type": "profile_warning",
                      "message": "目前使用範例履歷示意（非你本人背景）。"
                                 "請先到「自動找職缺」或「履歷健檢」提供你的履歷，再產生個人化投遞包。"})
    with _RUNS_LOCK:
        _prune_runs()
        _RUNS[thread_id] = run_obj
    run_obj.future = _RUN_EXECUTOR.submit(_run_pipeline_bg, run_obj, initial, config, _new_run_graph())
    return {"thread_id": thread_id, "package_id": pid}


@app.get("/api/run/events/{thread_id}")
def run_events(thread_id: str, since: int = 0):
    """輪詢某次背景產生的進度事件（since=已收到的事件數，重新整理時用 0 重播全部）。

    found=False 代表該 run 不在記憶體（已清理或伺服器重啟過）→ 前端改從『我的投遞包』載入結果。
    """
    run_obj = _RUNS.get(thread_id)
    if run_obj is None:
        return {"found": False, "events": [], "done": True}
    events, done = run_obj.snapshot(since)
    return {"found": True, "events": events, "done": done, "package_id": run_obj.package_id}


@app.post("/api/run/{thread_id}/stop")
def run_stop(thread_id: str):
    """Request a background run to stop and sync persisted status immediately."""
    run_obj = _RUNS.get(thread_id)
    if run_obj is None:
        return JSONResponse({"error": "找不到執行中的任務"}, status_code=404)
    run_obj.request_stop()
    try:
        if run_obj.future is not None:
            run_obj.future.cancel()
    except Exception:
        pass
    _history.set_status(run_obj.package_id, "stopped")
    return {"ok": True, "status": "stopped", "package_id": run_obj.package_id}


@app.post("/api/tasks/{task_id}/stop")
def task_stop(task_id: str):
    """Request a foreground SSE/JSON task to stop."""
    ok = task_control.request_stop(task_id)
    return {"ok": ok, "status": "stopped" if ok else "not_found"}


@app.get("/api/memory")
def memory_get():
    return _memory.get_memory()


class PreferencesBody(BaseModel):
    preferences: dict


class ProfileMemoryBody(BaseModel):
    profile: dict


@app.post("/api/memory")
def memory_post(body: PreferencesBody):
    _memory.save_preferences(body.preferences)
    return {"ok": True}


@app.put("/api/memory/profile")
def memory_profile_put(body: ProfileMemoryBody):
    try:
        profile = Profile(**body.profile)
        if not (profile.name.strip() or profile.summary.strip()):
            raise ValueError("profile missing name and summary")
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"error": f"履歷資料無法使用，請重新上傳履歷再試。（{_err_detail(exc)}）"},
            status_code=400)
    _memory.save_profile(profile.model_dump())
    return {"ok": True}


@app.delete("/api/memory/profile")
def memory_profile_delete():
    _memory.clear_profile()
    return {"ok": True}


@app.delete("/api/privacy-data")
def privacy_data_delete():
    """Clear locally stored resume/profile data, saved searches, and generated packages."""
    _memory.clear_memory()
    _searches.delete_all_searches()
    _resume_checks.delete_all_checks()
    _history.delete_all_packages()
    with _RUNS_LOCK:
        _RUNS.clear()
    return {"ok": True}


@app.get("/api/diagnostics")
def diagnostics_get():
    return {
        "error_log": str(_ERROR_LOG),
        "log_dir": str(_ERROR_LOG.parent),
        "app_db": os.environ.get("COPILOT_APP_DB", str(_ROOT / "data" / "app.sqlite")),
    }


@app.post("/api/diagnostics/open-log-folder")
def diagnostics_open_log_folder():
    _ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        _open_folder(_ERROR_LOG.parent)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return {"ok": True}


@app.get("/api/history")
def history_list():
    return {"packages": _history.list_packages()}


@app.get("/api/history/{pid}")
def history_get(pid: int):
    pkg = _history.get_package(pid)
    if pkg is None:
        return JSONResponse({"error": "找不到該投遞包"}, status_code=404)
    return pkg


@app.post("/api/history/{pid}/approve")
def history_approve(pid: int):
    _history.set_approved(pid, True)
    return {"ok": True}


@app.delete("/api/history/{pid}")
def history_delete(pid: int):
    _history.delete_package(pid)
    return {"ok": True}


@app.get("/api/resume/checks")
def resume_checks_list():
    return {"checks": _resume_checks.list_checks()}


@app.get("/api/resume/checks/{cid}")
def resume_checks_get(cid: int):
    check = _resume_checks.get_check(cid)
    if check is None:
        return JSONResponse({"error": "找不到該健檢紀錄"}, status_code=404)
    return check


@app.delete("/api/resume/checks/{cid}")
def resume_checks_delete(cid: int):
    _resume_checks.delete_check(cid)
    return {"ok": True}


class SearchSaveBody(BaseModel):
    label: str = ""
    profile: dict | None = None
    payload: dict = {}


@app.post("/api/searches")
def searches_save(body: SearchSaveBody):
    sid = _searches.save_search(body.label, body.profile, body.payload or {})
    return {"id": sid}


@app.get("/api/searches")
def searches_list():
    return {"searches": _searches.list_searches()}


@app.get("/api/searches/{sid}")
def searches_get(sid: int):
    s = _searches.get_search(sid)
    if s is None:
        return JSONResponse({"error": "找不到該搜尋紀錄"}, status_code=404)
    return s


@app.delete("/api/searches/{sid}")
def searches_delete(sid: int):
    _searches.delete_search(sid)
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index():
    dist_index = _FRONTEND_DIST / "index.html"
    if dist_index.exists():
        return dist_index.read_text(encoding="utf-8")
    return HTMLResponse(
        "<h1>前端尚未建置</h1><p>請先執行 <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>，"
        "再重新整理。</p>", status_code=503)


# dist 根目錄的靜態檔（favicon 等）不在 /assets 底下，需個別提供；
# 否則 /favicon.svg 會 404，瀏覽器分頁圖示沿用預設或舊快取（換了 logo 也看不到）。
def _serve_root_static(name: str, media: str):
    f = _FRONTEND_DIST / name
    if f.exists():
        return FileResponse(str(f), media_type=media)
    return Response(status_code=404)


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg():
    return _serve_root_static("favicon.svg", "image/svg+xml")


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico():
    # 沒有 .ico；回 svg（瀏覽器自動請求 /favicon.ico 時也不再 404）。
    return _serve_root_static("favicon.svg", "image/svg+xml")


@app.get("/logo512.png", include_in_schema=False)
def logo512():
    return _serve_root_static("logo512.png", "image/png")


@app.get("/icons.svg", include_in_schema=False)
def icons_svg():
    return _serve_root_static("icons.svg", "image/svg+xml")
