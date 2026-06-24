"""Eval harness：量測『反思迴圈關 vs 開』對投遞包品質的提升（用數字證明反思有效）。

- run_case：對單一 golden 案例跑整張 graph（真 LLM），回傳最終 CritiqueReport。
  反思「關」= 把 MAX_REVISIONS 設 0（critic 一過就送核可，不重寫）；
  反思「開」= 預設 MAX_REVISIONS（supervisor 決定是否重寫未過文件）。
- summarize：純函式，彙整 pass-rate 與平均分提升（可單元測試，不需真 LLM）。
- main：跑全部案例、印出比較、寫 JSON，數字可放進 README。

執行：python -m app.evals.harness   （需 claude_cli 或 anthropic 後端、會真的呼叫 LLM）
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from app import graph as graph_mod
from app.evals.fixtures import GOLDEN


def run_case(case: dict, max_revisions: int) -> object | None:
    """跑單一案例到人工核可關卡，回傳最終 CritiqueReport（被 match 擋下則 None）。"""
    from langgraph.checkpoint.memory import MemorySaver
    old = graph_mod.MAX_REVISIONS
    graph_mod.MAX_REVISIONS = max_revisions
    try:
        g = graph_mod.build_graph(checkpointer=MemorySaver())
        cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
        initial = {
            "jd_text": case["jd_text"], "profile": case["profile"],
            "parsed_job": None, "match_report": None, "supervisor_decision": None,
            "company_brief": None, "tailored_resume": None, "cover_letter": None,
            "interview_kit": None, "critique": None, "revision_count": 0,
            "approved": None, "errors": [], "telemetry": [],
        }
        g.invoke(initial, cfg)
        return g.get_state(cfg).values.get("critique")
    finally:
        graph_mod.MAX_REVISIONS = old


def _overall(report) -> float:
    return (report.resume_score + report.cover_letter_score + report.interview_score) / 3


def summarize(rows: list[dict]) -> dict:
    """rows: [{name, off: CritiqueReport|None, on: CritiqueReport|None}, ...] → 比較摘要（純函式）。"""
    off = [r["off"] for r in rows if r.get("off")]
    on = [r["on"] for r in rows if r.get("on")]

    def pass_rate(reps):
        return round(100 * sum(1 for r in reps if r.overall_pass) / len(reps), 1) if reps else 0.0

    def mean(reps):
        return round(sum(_overall(r) for r in reps) / len(reps), 1) if reps else 0.0

    return {
        "n": len(rows),
        "pass_rate_off": pass_rate(off),
        "pass_rate_on": pass_rate(on),
        "mean_off": mean(off),
        "mean_on": mean(on),
        "mean_lift": round(mean(on) - mean(off), 1),
        "pass_rate_lift": round(pass_rate(on) - pass_rate(off), 1),
    }


def main() -> None:
    rows = []
    for case in GOLDEN:
        print(f"[eval] {case['name']} — 反思關…")
        off = run_case(case, max_revisions=0)
        print(f"[eval] {case['name']} — 反思開…")
        on = run_case(case, max_revisions=3)
        rows.append({"name": case["name"], "off": off, "on": on})

    summary = summarize(rows)
    print("\n=== 反思迴圈評測結果 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    out = Path(__file__).parent / "results.json"
    out.write_text(json.dumps({
        "summary": summary,
        "rows": [{"name": r["name"],
                  "off": r["off"].model_dump() if r["off"] else None,
                  "on": r["on"].model_dump() if r["on"] else None} for r in rows],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已寫入 {out}")


if __name__ == "__main__":
    main()
