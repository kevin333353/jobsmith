"""多輪面試模擬 agent：出題 → 逐題即時回饋 → 總評（standard 分層）。

無狀態：對話歷程由前端持有；每次呼叫獨立。出題依職缺 + 履歷混合技術/行為/台灣特有題。
"""
from app.llm import get_llm
from app.models import (
    Profile, InterviewQuestion, InterviewQuestionList, AnswerFeedback, InterviewSummary,
)

_Q_SYSTEM = (
    "你是資深技術面試官，熟悉台灣求職市場。請依職缺與求職者背景，設計一場面試的題目，"
    "混合技術題、行為題與台灣特有題（自傳/期望薪資/為什麼想加入）。題目要具體、可作答，"
    "由淺入深。每題標註 category（技術/行為/台灣特有）。"
)
_FB_SYSTEM = (
    "你是面試教練。針對求職者對某題的回答，給出建設性即時回饋："
    "score（0-100）、strengths（答得好的點）、improvements（可改進處，具體可照做）、"
    "sample_answer（一個更好的示範答法，繁中、用 STAR 精神）。只根據回答內容評估，誠實但鼓勵。"
)
_SUM_SYSTEM = (
    "你是面試教練。看完整場面試逐字後，給總評：overall_score（0-100）、"
    "summary（一段整體表現總評）、advice（接下來最該補強的 3 點建議）。繁中。"
)


def generate_questions(jd: str, profile: Profile, n: int = 6) -> list[InterviewQuestion]:
    human = (f"【職缺】\n{jd}\n\n【求職者背景】\n{profile.model_dump_json(indent=2)}\n\n"
             f"請設計 {n} 題面試題。")
    llm = get_llm("standard").with_structured_output(InterviewQuestionList)
    out = llm.invoke([("system", _Q_SYSTEM), ("human", human)])
    return out.items[:n]


def evaluate_answer(question: str, answer: str, jd: str, profile: Profile) -> AnswerFeedback:
    human = (f"【職缺】\n{jd}\n\n【題目】\n{question}\n\n【求職者的回答】\n{answer}\n\n"
             f"【求職者背景】\n{profile.model_dump_json(indent=2)}")
    llm = get_llm("standard").with_structured_output(AnswerFeedback)
    return llm.invoke([("system", _FB_SYSTEM), ("human", human)])


def summarize(jd: str, transcript: list[dict]) -> InterviewSummary:
    body = "\n\n".join(
        f"Q: {t.get('question', '')}\nA: {t.get('answer', '')}" for t in transcript)
    human = f"【職缺】\n{jd}\n\n【面試逐字】\n{body}"
    llm = get_llm("standard").with_structured_output(InterviewSummary)
    return llm.invoke([("system", _SUM_SYSTEM), ("human", human)])
