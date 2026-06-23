"""④ 求職信/自傳 Agent。"""
from app.llm import get_llm
from app.models import ParsedJob, Profile, CompanyBrief, CoverLetter

COVER_SYSTEM = (
    "你是求職文案專家。請以台灣求職文化撰寫一封繁中求職信/自傳，"
    "對應職缺需求、凸顯求職者的相關經歷。"
    "若提供了公司情報，請自然地引用真實公司事實（例如募資、產品、文化），"
    "並把引用到的事實列在 company_facts_used。沒有公司情報就不要杜撰。"
)


def write_cover_letter(job: ParsedJob, profile: Profile, company: CompanyBrief | None) -> CoverLetter:
    """撰寫求職信/自傳（standard 分層）。"""
    company_json = company.model_dump_json(indent=2) if company else "（無公司情報）"
    human = (
        "【職缺】\n"
        f"{job.model_dump_json(indent=2)}\n\n"
        "【求職者背景】\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        "【公司情報】\n"
        f"{company_json}"
    )
    llm = get_llm("standard").with_structured_output(CoverLetter)
    return llm.invoke([("system", COVER_SYSTEM), ("human", human)])
