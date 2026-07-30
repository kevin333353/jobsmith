"""② 匹配 Agent：對 ParsedJob 與 Profile 打分。"""
from app.agents.prompt_context import profile_prompt_json
from app.llm import get_llm
from app.models import MatchReport, ParsedJob, Profile

MATCH_SYSTEM = (
    "你是資深技術招募顧問。請比對『職缺』與『求職者背景』，"
    "給 0-100 的匹配分數，列出符合項、落差項、補強建議，"
    "並判斷是否建議繼續產出投遞包（recommend_proceed）與理由。"
    "評分必須有依據，引用雙方的具體對應點，不要空泛。"
)


def match_profile(job: ParsedJob, profile: Profile) -> MatchReport:
    """比對職缺與求職者，回傳 MatchReport（使用 standard 分層）。"""
    llm = get_llm("standard").with_structured_output(MatchReport)
    human = (
        "【職缺】\n"
        f"{job.model_dump_json(indent=2)}\n\n"
        "【求職者背景】\n"
        f"{profile_prompt_json(profile)}"
    )
    return llm.invoke([("system", MATCH_SYSTEM), ("human", human)])
