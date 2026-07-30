"""③ 履歷客製 Agent：針對單一職缺改寫履歷。"""
from app.agents.prompt_context import profile_prompt_json
from app.llm import get_llm
from app.models import ParsedJob, Profile, TailoredResume

RESUME_SYSTEM = (
    "你是資深履歷顧問。請依『職缺』改寫『求職者』的履歷，"
    "挑選並重寫最相關的經歷條列，命中 JD 的 ATS 關鍵字，"
    "並列出已命中與尚缺的關鍵字。"
    "嚴禁捏造求職者沒有的經歷；只能重組與強調既有內容。"
)


def tailor_resume(job: ParsedJob, profile: Profile, feedback: list[str] | None = None) -> TailoredResume:
    """針對職缺客製履歷（standard 分層）；feedback 為上一輪品管意見。"""
    llm = get_llm("standard").with_structured_output(TailoredResume)
    human = (
        "【職缺】\n"
        f"{job.model_dump_json(indent=2)}\n\n"
        "【求職者背景】\n"
        f"{profile_prompt_json(profile, job=job, include_relevant_raw=True)}"
    )
    if feedback:
        human += "\n\n【品管意見，請據此改進】\n" + "\n".join(f"- {f}" for f in feedback)
    return llm.invoke([("system", RESUME_SYSTEM), ("human", human)])
