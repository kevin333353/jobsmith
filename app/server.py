"""FastAPI：以 SSE 串流跑反思迴圈圖，並用 HTTP 處理 human-in-the-loop。"""
import json
import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, Body
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.types import Command

from app import settings
from app.cli import load_profile
from app.graph import build_graph
from app.models import Profile
from app.intake.resume_parser import extract_text
from app.agents.resume_eval import structure_profile, evaluate_resume
from app.agents.job_search import derive_queries, rank_jobs
from app.sources.registry import search_all, linkedin_search_url

app = FastAPI(title="台灣 AI 求職 Co-pilot")

# 單一圖實例：/run 與 /resume 共用同一個 MemorySaver（per-process）。
GRAPH = build_graph()

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


def _stream(graph_input, config):
    """跑 graph.stream(updates)，逐節點 yield SSE；結束時判斷是否停在 interrupt。

    telemetry 由每個節點的 _safe 自行 begin/end（不在這裡 start_run——同步產生器被
    Starlette 丟 threadpool 時 contextvar 不跨 next() 存活，集中式蒐集會掉資料）。
    """
    for chunk in GRAPH.stream(graph_input, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                continue
            update = update or {}
            # 優雅降級：該節點 agent 失敗（已回降級 artifact）時，額外發 node_error 提示前端。
            for err in update.get("errors") or []:
                yield _sse({"type": "node_error", "node": err.get("node", node),
                            "message": err.get("message", "")})
            # telemetry：逐節點 token/成本/延遲（供前端顯示 agent 工程的可觀測性）。
            for t in update.get("telemetry") or []:
                yield _sse({"type": "telemetry", **t})
            yield _sse({"type": "node", "node": node, "data": serialize_update(update)})
    snapshot = GRAPH.get_state(config)
    if snapshot.next:  # 還有待跑節點 → 停在 human_gate interrupt
        payload = {}
        try:
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                payload = snapshot.tasks[0].interrupts[0].value
        except Exception:
            payload = {}
        yield _sse({"type": "interrupt",
                    "thread_id": config["configurable"]["thread_id"],
                    "payload": payload})
    else:
        yield _sse({"type": "done"})


class RunBody(BaseModel):
    jd_text: str
    # 使用者真實履歷結構（由 /api/jobs/auto 或 /api/resume/evaluate 的 profile 事件帶入）。
    # 缺省時才退回 demo profile（CLI / 測試後備）。
    profile: dict | None = None
    profile_path: str = "data/demo_profile.json"


class ResumeBody(BaseModel):
    thread_id: str
    decision: str


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


@app.post("/api/jobs/auto")
def jobs_auto(
    file: UploadFile | None = File(default=None),
    resume_text: str = Form(default=""),
):
    """履歷 → 自動找職缺：解析履歷 → 推導關鍵字 → 搜尋多站 → 依履歷排序。"""
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
            # 把使用者真實履歷（含 raw_text 原文）送給前端，供「產生投遞包」時整包帶入 pipeline，
            # 讓 match/resume/cover/interview agent 拿到逐字履歷（檔案上傳時前端沒有原文，必須由後端帶）。
            yield _sse({"type": "profile", "data": profile.model_dump()})
            queries = derive_queries(profile)
            yield _sse({"type": "queries", "queries": queries})

            seen: set[str] = set()
            all_jobs = []
            all_blocked = True
            for q in queries[:2]:
                yield _sse({"type": "progress", "step": "search", "message": f"搜尋「{q}」中…"})
                for res in search_all(q, limit=10):
                    if not res.blocked:
                        all_blocked = False
                    yield _sse({"type": "source", "source": res.source,
                                "count": len(res.jobs), "blocked": res.blocked})
                    for j in res.jobs:
                        key = j.url or (j.title + j.company)
                        if key in seen:
                            continue
                        seen.add(key)
                        all_jobs.append(j)

            # 誠實降級：所有來源失敗或零結果 → 告知並改用後備樣本職缺，demo 永遠有東西看。
            used_fallback = False
            if not all_jobs:
                used_fallback = True
                yield _sse({"type": "all_blocked",
                            "message": "即時職缺來源暫時取得不到結果，以下改用範例職缺示意，"
                                       "並請改用下方 LinkedIn / 104 直連搜尋。"})
                all_jobs = _load_fallback_jobs()

            yield _sse({"type": "progress", "step": "rank",
                        "message": f"依履歷排序 {len(all_jobs)} 筆職缺…"})
            matches = rank_jobs(profile, all_jobs, top_k=12)
            yield _sse({"type": "jobs", "data": [m.model_dump() for m in matches],
                        "fallback": used_fallback})
            yield _sse({"type": "linkedin", "url": linkedin_search_url(queries[0] if queries else "")})
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
    """偵測該後端是否可用：CLI 看執行檔在不在 PATH；anthropic 看有沒有金鑰。"""
    if name == "claude_cli":
        return bool(os.environ.get("CLAUDE_CLI_PATH") or shutil.which("claude"))
    if name == "codex_cli":
        return bool(os.environ.get("CODEX_CLI_PATH") or shutil.which("codex"))
    if name == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return False


@app.get("/api/backend")
def get_backend():
    """目前作用中的 LLM 後端與可選清單（供 UI 切換 Claude Code CLI / Codex CLI）。"""
    return {
        "current": settings.current_backend(),
        "options": [
            {"id": b, "label": settings.BACKEND_LABELS.get(b, b), "available": _backend_available(b)}
            for b in settings.SUPPORTED_BACKENDS
        ],
    }


class BackendBody(BaseModel):
    backend: str


@app.post("/api/backend")
def post_backend(body: BackendBody):
    """切換 LLM 後端（執行期，單人本機）。後續每個 agent 呼叫即採用新後端。"""
    try:
        settings.set_backend(body.backend)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"current": settings.current_backend()}


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


@app.post("/api/run")
def run(body: RunBody):
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    def gen():
        yield _sse({"type": "start", "thread_id": thread_id})
        # 在 generator 內解析履歷，壞/缺履歷回友善 SSE error 而非 500（與其他端點一致）。
        try:
            profile = _resolve_profile(body)
        except Exception as exc:
            yield _sse({"type": "error",
                        "message": f"履歷資料無法使用，請重新上傳履歷再試。（{type(exc).__name__}）"})
            return
        # 沒帶真實履歷 → 用範例 demo，明確提醒使用者（避免把假人投遞包當成自己的）。
        if not body.profile:
            yield _sse({"type": "profile_warning",
                        "message": "目前使用範例履歷示意（非你本人背景）。"
                                   "請先到「自動找職缺」或「履歷健檢」提供你的履歷，再產生個人化投遞包。"})
        initial = {
            "jd_text": body.jd_text, "profile": profile,
            "parsed_job": None, "match_report": None, "supervisor_decision": None,
            "company_brief": None, "tailored_resume": None, "cover_letter": None,
            "interview_kit": None, "critique": None, "revision_count": 0,
            "approved": None, "errors": [], "telemetry": [],
        }
        yield from _stream(initial, config)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/resume")
def resume(body: ResumeBody):
    config = {"configurable": {"thread_id": body.thread_id}}

    def gen():
        yield _sse({"type": "start", "thread_id": body.thread_id})
        yield from _stream(Command(resume=body.decision), config)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
def index():
    dist_index = _FRONTEND_DIST / "index.html"
    if dist_index.exists():
        return dist_index.read_text(encoding="utf-8")
    return HTMLResponse(
        "<h1>前端尚未建置</h1><p>請先執行 <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>，"
        "再重新整理。</p>", status_code=503)
