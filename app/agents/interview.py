"""⑤ 面試準備 Agent。"""
from app.llm import get_llm
from app.models import ParsedJob, Profile, CompanyBrief, InterviewKit

INTERVIEW_SYSTEM = (
    "你是面試教練。請依職缺與求職者背景，準備面試包："
    "技術題、行為題、台灣特有題（自傳、期望薪資、為什麼想加入）、"
    "對應的 STAR 擬答、給求職者用的反向提問。"
    "若提供公司情報，請加入公司近況考點與避雷提醒（依紅旗）。"
)


def prepare_interview(job: ParsedJob, profile: Profile, company: CompanyBrief | None) -> InterviewKit:
    """準備面試包（standard 分層）。"""
    company_json = company.model_dump_json(indent=2) if company else "（無公司情報）"
    human = (
        "【職缺】\n"
        f"{job.model_dump_json(indent=2)}\n\n"
        "【求職者背景】\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        "【公司情報】\n"
        f"{company_json}"
    )
    llm = get_llm("standard").with_structured_output(InterviewKit)
    return llm.invoke([("system", INTERVIEW_SYSTEM), ("human", human)])
