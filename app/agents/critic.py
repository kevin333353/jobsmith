"""⑥ 品管/反思 Agent：對投遞包評分並給修改指示。"""
from app.llm import get_llm
from app.models import (
    ParsedJob, TailoredResume, CoverLetter, InterviewKit, CritiqueReport,
)

CRITIC_SYSTEM = (
    "你是嚴格的投遞包品管審查員。請依『職缺』，對『客製履歷、求職信、面試準備』"
    "三份成品逐項評分（0-100），並判斷整體是否達標（overall_pass）。"
    "評分依據：是否命中 JD 必備條件、ATS 關鍵字覆蓋、台灣在地規範與語氣、"
    "是否具體不空泛、是否有捏造未提供的經歷。"
    "若未達標，feedback 必須是可執行的具體修改指示（給下一輪重寫用）。"
)


def critique_package(
    job: ParsedJob,
    resume: TailoredResume,
    cover_letter: CoverLetter,
    interview_kit: InterviewKit,
) -> CritiqueReport:
    """評審投遞包（deep 分層）。"""
    llm = get_llm("deep").with_structured_output(CritiqueReport)
    human = (
        f"【職缺】\n{job.model_dump_json(indent=2)}\n\n"
        f"【客製履歷】\n{resume.model_dump_json(indent=2)}\n\n"
        f"【求職信】\n{cover_letter.model_dump_json(indent=2)}\n\n"
        f"【面試準備】\n{interview_kit.model_dump_json(indent=2)}"
    )
    return llm.invoke([("system", CRITIC_SYSTEM), ("human", human)])
