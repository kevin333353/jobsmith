"""終端機進入點：讀 JD → 跑反思迴圈圖 → 人工核可 → 印完整投遞包。"""
import json
import sys
import uuid
from pathlib import Path

from langgraph.types import Command

from app.models import Profile
from app.state import CopilotState
from app.graph import build_graph


def load_profile(path: str = "data/demo_profile.json") -> Profile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Profile(**data)


def _join(items: list[str]) -> str:
    return "、".join(items) if items else "（無）"


def format_output(state: dict, job_title: str) -> str:
    report = state["match_report"]
    lines = [
        f"=== 匹配報告：{job_title} ===",
        f"分數：{report.score}/100",
        f"建議續做：{'是' if report.recommend_proceed else '否'}（{report.reason}）",
        "符合項：" + _join(report.matched),
        "落差項：" + _join(report.gaps),
        "補強建議：" + _join(report.suggestions),
    ]

    company = state.get("company_brief")
    if company is not None:
        lines += [
            "",
            f"=== 公司情報：{company.company} ===",
            f"薪資範圍：{company.salary_range or '（無）'}",
            "福利：" + _join(company.benefits),
            "避雷紅旗：" + _join(company.red_flags),
        ]
        if company.data_limited:
            lines.append("（註：公開資料有限）")

    resume = state.get("tailored_resume")
    if resume is not None:
        lines += [
            "",
            "=== 客製履歷 ===",
            f"定位：{resume.summary}",
            "重點條列：" + _join(resume.bullets),
            "ATS 命中：" + _join(resume.ats_keywords_hit),
            "ATS 尚缺：" + _join(resume.ats_keywords_missing),
        ]

    letter = state.get("cover_letter")
    if letter is not None:
        lines += ["", "=== 求職信/自傳 ===", letter.body]

    kit = state.get("interview_kit")
    if kit is not None:
        lines += [
            "",
            "=== 面試準備 ===",
            "技術題：" + _join(kit.technical_questions),
            "行為題：" + _join(kit.behavioral_questions),
            "台灣特有題：" + _join(kit.taiwan_specific_questions),
            "反向提問：" + _join(kit.reverse_questions),
            "避雷提醒：" + _join(kit.cautions),
        ]

    critique = state.get("critique")
    if critique is not None:
        lines += [
            "",
            "=== 品管評審 ===",
            f"履歷 {critique.resume_score}／求職信 {critique.cover_letter_score}／面試 {critique.interview_score}",
            f"整體達標：{'是' if critique.overall_pass else '否'}",
            "修改意見：" + _join(critique.feedback),
        ]

    approved = state.get("approved")
    if approved is not None:
        lines += ["", f"=== 核可狀態：{'已核可' if approved else '未核可'} ==="]

    return "\n".join(lines)


def run(jd_path: str, profile_path: str = "data/demo_profile.json") -> CopilotState:
    jd_text = Path(jd_path).read_text(encoding="utf-8")
    profile = load_profile(profile_path)
    graph = build_graph()
    config = {"configurable": {"thread_id": uuid.uuid4().hex}}
    initial = {
        "jd_text": jd_text,
        "profile": profile,
        "parsed_job": None,
        "match_report": None,
        "company_brief": None,
        "tailored_resume": None,
        "cover_letter": None,
        "interview_kit": None,
        "critique": None,
        "revision_count": 0,
        "approved": None,
        "errors": [],
        "telemetry": [],
    }
    result = graph.invoke(initial, config)

    if "__interrupt__" in result:
        state_values = graph.get_state(config).values
        print(format_output(state_values, job_title=Path(jd_path).stem))
        decision = input("\n核可這份投遞包嗎？(y/n)：")
        graph.invoke(Command(resume=decision), config)

    return graph.get_state(config).values


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("用法：python -m app.cli <jd 檔案路徑>")
        return 1
    jd_path = argv[0]
    state = run(jd_path)
    print(format_output(state, job_title=Path(jd_path).stem))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
