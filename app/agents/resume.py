"""③ 履歷客製 Agent：針對單一職缺改寫履歷。"""
from app.llm import get_llm
from app.models import ParsedJob, Profile, TailoredResume

RESUME_SYSTEM = (
    "你是資深履歷顧問。請依『職缺』改寫『求職者』的履歷，"
    "挑選並重寫最相關的經歷條列，命中 JD 的 ATS 關鍵字，"
    "並列出已命中與尚缺的關鍵字。"
    "嚴禁捏造求職者沒有的經歷；只能重組與強調既有內容。"
)


def tailor_resume(job: ParsedJob, profile: Profile) -> TailoredResume:
    """針對職缺客製履歷（standard 分層）。"""
    llm = get_llm("standard").with_structured_output(TailoredResume)
    human = (
        "【職缺】\n"
        f"{job.model_dump_json(indent=2)}\n\n"
        "【求職者背景】\n"
        f"{profile.model_dump_json(indent=2)}"
    )
    return llm.invoke([("system", RESUME_SYSTEM), ("human", human)])
