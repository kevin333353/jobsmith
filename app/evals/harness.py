"""Eval harness：量測漸進式投遞包的一次性 AI 品管結果。

- run_case：對單一 golden 案例產出完整文件並跑一次品管（不自動重寫）。
- summarize：保留舊結果檔的 off/on 比較彙整（純函式）。
- main：跑全部案例一次、印出通過率與平均分、寫 JSON。

執行：python -m app.evals.harness   （需 claude_cli 或 anthropic 後端、會真的呼叫 LLM）
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from app import graph as graph_mod
from app.evals.fixtures import GOLDEN


def run_case(case: dict) -> object | None:
    """跑單一案例的一次性完整產出與品管；被 match 擋下則回 None。"""
    from langgraph.checkpoint.memory import MemorySaver

    g = graph_mod.build_graph(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
    initial = {
        "jd_text": case["jd_text"], "profile": case["profile"],
        "artifact_targets": ["resume", "cover_letter", "interview"],
        "company_research_requested": True, "quality_review": True,
        "parsed_job": None, "match_report": None, "supervisor_decision": None,
        "company_brief": None, "tailored_resume": None, "cover_letter": None,
        "interview_kit": None, "critique": None, "revision_count": 0,
        "approved": None, "batch": True, "errors": [], "telemetry": [],
    }
    g.invoke(initial, cfg)
    return g.get_state(cfg).values.get("critique")


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
        print(f"[eval] {case['name']} — 一次性完整產出＋品管…")
        report = run_case(case)
        rows.append({"name": case["name"], "report": report})

    reports = [row["report"] for row in rows if row["report"]]
    summary = {
        "n": len(rows),
        "reviewed": len(reports),
        "pass_rate": round(100 * sum(1 for report in reports if report.overall_pass)
                           / len(reports), 1) if reports else 0.0,
        "mean_score": round(sum(_overall(report) for report in reports)
                            / len(reports), 1) if reports else 0.0,
    }
    print("\n=== 漸進式投遞包評測結果 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    out = Path(__file__).parent / "results.json"
    out.write_text(json.dumps({
        "summary": summary,
        "rows": [{"name": row["name"],
                  "report": row["report"].model_dump() if row["report"] else None}
                 for row in rows],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已寫入 {out}")


if __name__ == "__main__":
    main()
