"""FastAPI：以 SSE 串流跑反思迴圈圖，並用 HTTP 處理 human-in-the-loop。"""
import json
import os
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, Body
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.checkpoint.memory import MemorySaver

from app import settings
from app.cli import load_profile
from app.graph import build_graph
from app.models import Profile, JobMatch
from app.intake.resume_parser import extract_text
from app.agents.resume_eval import structure_profile, evaluate_resume
from app.agents.job_search import derive_queries, rank_jobs
from app.agents.company_jobs import find_company_jobs
from app.sources.registry import search_all, linkedin_search_url
from app.sources import regions

from app.store import db as _appdb
from app.store import history as _history
from app.store import memory as _memory
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
        self.future = None
        self._lock = threading.Lock()

    def emit(self, ev: dict) -> None:
        with self._lock:
            self.events.append(ev)

    def finish(self) -> None:
        with self._lock:
            self.done = True

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
            for node, update in chunk.items():
                if node == "__interrupt__":
                    continue
                update = update or {}
                for err in update.get("errors") or []:
                    run.emit({"type": "node_error", "node": err.get("node", node),
                              "message": err.get("message", "")})
                for t in update.get("telemetry") or []:
                    run.emit({"type": "telemetry", **t})
                run.emit({"type": "node", "node": node, "data": serialize_update(update)})
        snapshot = graph.get_state(config)
        final = serialize_update(snapshot.values)
        _history.update_package_result(run.package_id, final)
        run.emit({"type": "done", "package_id": run.package_id})
    except Exception as exc:  # noqa: BLE001 — 背景出錯也要收尾，不讓那筆永遠卡「進行中」
        run.emit({"type": "error", "message": f"{type(exc).__name__}: {str(exc)[:200]}"})
        try:
            _history.set_status(run.package_id, "failed")
        except Exception:
            pass
    finally:
        run.finish()


class RunBody(BaseModel):
    jd_text: str
    # 使用者真實履歷結構（由 /api/jobs/auto 或 /api/resume/evaluate 的 profile 事件帶入）。
    # 缺省時才退回 demo profile（CLI / 測試後備）。
    profile: dict | None = None
    profile_path: str = "data/demo_profile.json"
    # 個人化偏好（語氣/目標職稱/年資/想強調技能）；套進 profile 讓各生成 agent 採用。
    preferences: dict | None = None
    # 批次模式：清單逐一無人值守產生時為 True，跳過互動核可、直接存成「待審」。
    batch: bool = False


# 注意：以下兩個串流端點用一般 def（非 async def），讓 Starlette 在 threadpool 執行
# 同步產生器，避免 claude_cli 的同步 subprocess 阻塞事件迴圈、卡住其他請求。
@app.post("/api/resume/evaluate")
def resume_evaluate(
    file: UploadFile | None = File(default=None),
    resume_text: str = Form(default=""),
):
    if file is not None:
        data = file.file.read()
        text = extract_text(data, file.filename or "resume.txt")
    else:
        text = resume_text

    def gen():
        yield _sse({"type": "start"})
        if not text.strip():
            yield _sse({"type": "error", "message": "請提供履歷檔案或文字"})
            return
        try:
            yield _sse({"type": "progress", "step": "structure", "message": "解析履歷中…"})
            profile = structure_profile(text)
            try:
                _memory.save_profile(profile.model_dump())  # 記住最近履歷（跨 session）
            except Exception:
                pass
            # 含 raw_text 原文，供使用者接著到「投遞包工作台」手動開跑時帶入本人背景。
            yield _sse({"type": "profile", "data": profile.model_dump()})
            yield _sse({"type": "progress", "step": "evaluate", "message": "健檢評估中…"})
            assessment = evaluate_resume(text, profile)
            yield _sse({"type": "assessment", "data": assessment})
            yield _sse({"type": "done"})
        except Exception as exc:  # LLM 後端 429/額度/截斷等：回傳友善訊息而非中斷串流
            yield _sse({"type": "error",
                        "message": f"AI 服務暫時無法使用，請稍後再試。（{type(exc).__name__}）"})

    return StreamingResponse(gen(), media_type="text/event-stream")


_RANK_BATCH = 12  # 每批送 LLM 排序的職缺數（批小→首批更快出現）


def _rank_in_batches(profile, jobs, batch: int = _RANK_BATCH, workers: int = 4):
    """把職缺切批、並行送 rank_jobs，哪批先完成就先 yield（供 SSE 邊排邊推）。

    並行多個 CLI 子行程：總時間≈一批，且首批很快就回；單批失敗該批以未評分(0)回，不中斷。
    """
    chunks = [jobs[i:i + batch] for i in range(0, len(jobs), batch)]
    if not chunks:
        return
    with ThreadPoolExecutor(max_workers=min(workers, len(chunks))) as ex:
        futs = {ex.submit(rank_jobs, profile, c, None): c for c in chunks}
        for fut in as_completed(futs):
            try:
                yield fut.result()
            except Exception:  # noqa: BLE001 — 單批失敗不影響其他批
                yield [JobMatch(job=j, fit_score=0, reason="未評分") for j in futs[fut]]


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
    companies: str = Form(default=""),
    pages: int = Form(default=2),
    region: str = Form(default=""),
):
    """履歷 → 自動找職缺：解析履歷 → 推導關鍵字 → 搜尋多站 →（選填）併入指定公司的開缺 → 依履歷排序。

    pages：每個來源抓幾頁（使用者可在前端調整，預設 2、夾在 1–5）。
    region：搜尋前選定的縣市（逗號串接 key）。對所有來源一致生效——104 於來源端用 area
            代碼篩選（涵蓋更全），其餘來源在結果端用 location 過濾，使用者看到的就是同一份地區結果。
    """
    pages = max(1, min(5, pages))
    region_keys = regions.parse_keys(region)
    area = regions.area_codes(region_keys)
    if file is not None:
        data = file.file.read()
        text = extract_text(data, file.filename or "resume.txt")
    else:
        text = resume_text
    company_list = _parse_companies(companies)

    def gen():
        yield _sse({"type": "start"})
        if not text.strip():
            yield _sse({"type": "error", "message": "請提供履歷檔案或文字"})
            return
        try:
            yield _sse({"type": "progress", "step": "structure", "message": "解析履歷中…"})
            profile = structure_profile(text)
            try:
                _memory.save_profile(profile.model_dump())  # 記住最近履歷（跨 session）
            except Exception:
                pass
            # 把使用者真實履歷（含 raw_text 原文）送給前端，供「產生投遞包」時整包帶入 pipeline，
            # 讓 match/resume/cover/interview agent 拿到逐字履歷（檔案上傳時前端沒有原文，必須由後端帶）。
            yield _sse({"type": "profile", "data": profile.model_dump()})
            queries = derive_queries(profile)
            yield _sse({"type": "queries", "queries": queries})

            seen: set[str] = set()
            resume_jobs = []
            for q in queries[:3]:
                yield _sse({"type": "progress", "step": "search", "message": f"搜尋「{q}」中…"})
                for res in search_all(q, limit=15, pages=pages, area=area):
                    # 104 已於來源端用 area 篩過；其餘來源在結果端依 location 過濾，地區一致生效。
                    kept = [j for j in res.jobs
                            if res.source == "104" or regions.match_location(j.location, region_keys)]
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
            if not resume_jobs:
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
            for batch in _rank_in_batches(profile, resume_jobs):
                matches.extend(batch)
                yield _sse({"type": "ranked_batch", "data": [m.model_dump() for m in batch]})
            li_loc = f"{region_keys[0]}, Taiwan" if region_keys else "Taiwan"
            yield _sse({"type": "linkedin",
                        "url": linkedin_search_url(queries[0] if queries else "", li_loc)})

            # ② 使用者指定的公司開缺：與 AI 搜尋『分開』收集、分開排序、分開顯示，
            # 避免低適配的公司職缺佔據 AI 推薦名單前段、又吃掉排序名額。
            company_pool = []
            for company in company_list:
                yield _sse({"type": "progress", "step": "company",
                            "message": f"查「{company}」的開缺中…"})
                try:
                    found = find_company_jobs(company, profile)
                except Exception:
                    found = []
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
                cmatches = rank_jobs(profile, company_pool, top_k=None)
                yield _sse({"type": "company_jobs",
                            "data": [m.model_dump() for m in cmatches]})
            yield _sse({"type": "done"})
        except Exception as exc:  # LLM/網路錯誤：友善降級
            yield _sse({"type": "error",
                        "message": f"AI 服務暫時無法使用，請稍後再試。（{type(exc).__name__}）"})

    return StreamingResponse(gen(), media_type="text/event-stream")


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
    from app.intake.jd_fetch import fetch_jd, JDFetchError
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
    """偵測該後端是否可用：CLI 看執行檔在不在 PATH；openai 看有金鑰或 base_url；anthropic 看金鑰。"""
    if name == "claude_cli":
        return bool(os.environ.get("CLAUDE_CLI_PATH") or shutil.which("claude"))
    if name == "codex_cli":
        return bool(os.environ.get("CODEX_CLI_PATH") or shutil.which("codex"))
    if name == "openai":  # 有金鑰，或有 base_url（如 Ollama / LM Studio 本機免金鑰）即可
        return bool(settings.byok_api_key() or settings.byok_base_url())
    if name == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return False


def _cli_version(name: str) -> str:
    """跑 `<cli> --version` 取版本字串（給設定面板的卡片顯示）；找不到/失敗回空字串。"""
    import subprocess
    spec = {"claude_cli": ("CLAUDE_CLI_PATH", "claude"),
            "codex_cli": ("CODEX_CLI_PATH", "codex")}.get(name)
    if not spec:
        return ""
    exe = os.environ.get(spec[0]) or shutil.which(spec[1])
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
    }


class BackendBody(BaseModel):
    backend: str


@app.post("/api/backend")
def post_backend(body: BackendBody):
    """切換 LLM 後端（執行期，單人本機）。選了即生效，不以測試結果為門檻。"""
    try:
        settings.set_backend(body.backend)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"current": settings.current_backend()}


class CliModelBody(BaseModel):
    backend: str
    model: str


@app.post("/api/backend/model")
def post_backend_model(body: CliModelBody):
    """設定某本機 CLI 後端要用的模型（'auto' = 自動分層）。"""
    try:
        settings.set_cli_model(body.backend, body.model)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"backend": body.backend, "model": settings.cli_model(body.backend)}


class ByokBody(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


@app.post("/api/backend/byok")
def post_backend_byok(body: ByokBody):
    """儲存 BYOK（OpenAI 相容）設定並寫回 .env；api_key 留空則保留既有金鑰。"""
    settings.set_byok(body.base_url, body.api_key, body.model)
    return {"byok": settings.byok_public()}


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


@app.post("/api/backend/test")
def test_backend(body: BackendBody):
    """實測指定後端是否能連線（真的跑一次極短的 CLI 呼叫），供開場引導畫面顯示連線狀態。

    不改動目前作用中的後端——測試與切換分開，測失敗不會把使用者切到壞掉的後端。
    """
    name = body.backend
    if name not in settings.SUPPORTED_BACKENDS:
        return JSONResponse({"ok": False, "message": "不支援的後端"}, status_code=400)
    if not _backend_available(name):
        return {"ok": False, "message": "找不到對應的 CLI 或金鑰，請確認已安裝並登入。"}
    try:
        if name == "claude_cli":
            out = _probe_claude()
        elif name == "codex_cli":
            out = _probe_codex()
        elif name == "openai":
            out = _probe_openai()
        else:  # anthropic
            from langchain_anthropic import ChatAnthropic
            out = ChatAnthropic(model=settings.get_model("cheap"), max_tokens=50).invoke(
                [("human", "只回覆兩個字：你好")]).content
        ok = bool((out or "").strip())
        return {"ok": ok, "message": "連線成功" if ok else "回覆為空，請重試。"}
    except Exception as e:  # noqa: BLE001 — 任何 CLI/網路錯誤都回友善訊息
        return {"ok": False, "message": f"連線失敗（{type(e).__name__}），請確認 CLI 已登入。"}


class InterviewStartBody(BaseModel):
    jd_text: str
    profile: dict | None = None
    n: int = 6
    profile_path: str = "data/demo_profile.json"


class InterviewAnswerBody(BaseModel):
    jd_text: str
    question: str
    answer: str
    profile: dict | None = None
    profile_path: str = "data/demo_profile.json"


class InterviewSummaryBody(BaseModel):
    jd_text: str
    transcript: list[dict]


@app.post("/api/interview/start")
def interview_start(body: InterviewStartBody):
    from app.agents.interview_sim import generate_questions
    try:
        profile = _resolve_profile(body)
        qs = generate_questions(body.jd_text, profile, n=body.n)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{type(exc).__name__}）"},
                            status_code=400)
    return {"questions": [q.model_dump() for q in qs]}


@app.post("/api/interview/answer")
def interview_answer(body: InterviewAnswerBody):
    from app.agents.interview_sim import evaluate_answer
    try:
        profile = _resolve_profile(body)
        fb = evaluate_answer(body.question, body.answer, body.jd_text, profile)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{type(exc).__name__}）"},
                            status_code=400)
    return fb.model_dump()


class PipelineChatBody(BaseModel):
    doc_type: str = "resume"          # resume | cover
    current: str = ""                 # 目前文件內容（供上下文）
    jd_text: str = ""
    profile: dict | None = None
    profile_path: str = "data/demo_profile.json"
    messages: list[dict] = []          # [{role: user|assistant, content}]


@app.post("/api/pipeline/chat")
def pipeline_chat(body: PipelineChatBody):
    """履歷／求職信的多輪對話修改：回覆建議，並（必要時）回傳修訂後的文件欄位。"""
    from app.agents.refine import refine_document
    try:
        profile = _resolve_profile(body)
        res = refine_document(body.doc_type, body.current, body.messages, body.jd_text, profile)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{type(exc).__name__}）"},
                            status_code=400)
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
    try:
        s = summarize(body.jd_text, body.transcript)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"AI 服務暫時無法使用，請稍後再試。（{type(exc).__name__}）"},
                            status_code=400)
    return s.model_dump()


def _resolve_profile(body: RunBody) -> Profile:
    """優先用使用者真實履歷；缺省才退回 demo profile。"""
    if body.profile:
        data = dict(body.profile)
        data.setdefault("raw_text", "")  # raw_text 為必填，前端事件已排除，補空字串
        return Profile(**data)
    profile_path = body.profile_path
    if not Path(profile_path).is_absolute():
        profile_path = str(_ROOT / profile_path)
    return load_profile(profile_path)


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
            {"error": f"履歷資料無法使用，請重新上傳履歷再試。（{type(exc).__name__}）"},
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


@app.get("/api/memory")
def memory_get():
    return _memory.get_memory()


class PreferencesBody(BaseModel):
    preferences: dict


@app.post("/api/memory")
def memory_post(body: PreferencesBody):
    _memory.save_preferences(body.preferences)
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
