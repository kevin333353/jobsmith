"""FastAPI：以 SSE 串流跑反思迴圈圖，並用 HTTP 處理 human-in-the-loop。"""
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.types import Command

from app.cli import load_profile
from app.graph import build_graph
from app.intake.resume_parser import extract_text
from app.agents.resume_eval import structure_profile, evaluate_resume

app = FastAPI(title="台灣 AI 求職 Co-pilot")

# 單一圖實例：/run 與 /resume 共用同一個 MemorySaver（per-process）。
GRAPH = build_graph()

_WEB_DIR = Path(__file__).parent / "web"
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
    """跑 graph.stream(updates)，逐節點 yield SSE；結束時判斷是否停在 interrupt。"""
    for chunk in GRAPH.stream(graph_input, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                continue
            yield _sse({"type": "node", "node": node, "data": serialize_update(update or {})})
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
    profile_path: str = "data/demo_profile.json"


class ResumeBody(BaseModel):
    thread_id: str
    decision: str


@app.post("/api/resume/evaluate")
async def resume_evaluate(
    file: UploadFile | None = File(default=None),
    resume_text: str = Form(default=""),
):
    if file is not None:
        data = await file.read()
        text = extract_text(data, file.filename or "resume.txt")
    else:
        text = resume_text

    def gen():
        yield _sse({"type": "start"})
        if not text.strip():
            yield _sse({"type": "error", "message": "請提供履歷檔案或文字"})
            return
        yield _sse({"type": "progress", "step": "structure", "message": "解析履歷中…"})
        profile = structure_profile(text)
        yield _sse({"type": "profile", "data": profile})
        yield _sse({"type": "progress", "step": "evaluate", "message": "健檢評估中…"})
        assessment = evaluate_resume(text, profile)
        yield _sse({"type": "assessment", "data": assessment})
        yield _sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/sample")
def sample():
    jd = (_ROOT / "data" / "demo_jobs" / "ai_engineer.txt").read_text(encoding="utf-8")
    return {"jd_text": jd}


@app.post("/api/run")
def run(body: RunBody):
    profile_path = body.profile_path
    if not Path(profile_path).is_absolute():
        profile_path = str(_ROOT / profile_path)
    profile = load_profile(profile_path)
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    initial = {
        "jd_text": body.jd_text, "profile": profile,
        "parsed_job": None, "match_report": None, "company_brief": None,
        "tailored_resume": None, "cover_letter": None, "interview_kit": None,
        "critique": None, "revision_count": 0, "approved": None,
    }

    def gen():
        yield _sse({"type": "start", "thread_id": thread_id})
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
    return (_WEB_DIR / "index.html").read_text(encoding="utf-8")
