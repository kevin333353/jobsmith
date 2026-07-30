"""⑥ 選配 AI 品管：對本次選擇的成品評分並給人工修改建議。"""
from app.llm import get_llm
from app.models import (
    CoverLetter,
    CritiqueReport,
    InterviewKit,
    ParsedJob,
    TailoredResume,
)

CRITIC_SYSTEM = (
    "你是嚴格的投遞包品管審查員。請依『職缺』，只審查使用者這次提供的成品，"
    "對有提供的客製履歷、求職信或面試準備逐項評分（0-100），並判斷整體是否達標。"
    "評分依據：是否命中 JD 必備條件、ATS 關鍵字覆蓋、台灣在地規範與語氣、"
    "是否具體不空泛、是否有捏造未提供的經歷。"
    "未提供的文件分數固定填 100，且不得為它提供建議。若有問題，請把可執行的人工修改建議"
    "放進 per_doc，鍵只能用 resume / cover_letter / interview，且只放有提供、需要改善的文件。"
    "系統不會自動重寫，建議必須讓使用者能直接判斷與採用。"
)


def critique_package(
    job: ParsedJob,
    resume: TailoredResume | None = None,
    cover_letter: CoverLetter | None = None,
    interview_kit: InterviewKit | None = None,
) -> CritiqueReport:
    """一次審查本次實際產出的文件；不觸發重寫。"""
    if not any((resume, cover_letter, interview_kit)):
        raise ValueError("沒有可供 AI 品管的成品")
    llm = get_llm("deep").with_structured_output(CritiqueReport)
    sections = [f"【職缺】\n{job.model_dump_json(indent=2)}"]
    if resume is not None:
        sections.append(f"【客製履歷】\n{resume.model_dump_json(indent=2)}")
    if cover_letter is not None:
        sections.append(f"【求職信】\n{cover_letter.model_dump_json(indent=2)}")
    if interview_kit is not None:
        sections.append(f"【面試準備】\n{interview_kit.model_dump_json(indent=2)}")
    human = "\n\n".join(sections)
    report = llm.invoke([("system", CRITIC_SYSTEM), ("human", human)])
    selected = {
        "resume": resume is not None,
        "cover_letter": cover_letter is not None,
        "interview": interview_kit is not None,
    }
    # 未選文件不應污染分數或建議；固定 100 也維持舊 schema/歷史資料相容。
    for doc, present in selected.items():
        if not present:
            setattr(report, f"{doc}_score", 100)
    report.per_doc = {
        doc: items for doc, items in (report.per_doc or {}).items()
        if selected.get(doc) and items
    }
    # 由 per_doc 彙整 feedback（前端相容；標註文件別）。
    _DOC_LABEL = {"resume": "履歷", "cover_letter": "求職信", "interview": "面試"}
    report.feedback = [
        f"[{_DOC_LABEL.get(doc, doc)}] {item}"
        for doc, items in (report.per_doc or {}).items() for item in items
    ]
    return report
