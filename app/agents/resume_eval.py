"""② 履歷健檢 Agent：把履歷全文結構化成 Profile，並做健檢評分。"""
from app.llm import get_llm
from app.models import Profile, ResumeAssessment

STRUCTURE_SYSTEM = (
    "你是履歷解析器。請從使用者提供的履歷全文中，抽取結構化欄位："
    "姓名(name)、一句話定位(summary)、技能清單(skills)、經歷條列(experiences)、"
    "學歷(education)、總年資(years_experience)、期望職務(preferred_roles)。"
    "raw_text 欄位請直接填入空字串即可（系統會自行補上原文，不需你回填）。"
    "找不到的欄位留空或 null，不要捏造。"
)

EVAL_SYSTEM = (
    "你是資深台灣科技業招募顧問暨履歷健檢專家。請依台灣求職與 ATS 慣例，對這份履歷評分"
    "（每項 0-100）：整體(overall_score)、表達清晰度(clarity_score)、量化成果(impact_score)、"
    "ATS 關鍵字涵蓋(ats_keyword_score)、台灣履歷慣例符合度(localization_score)、完整度(completeness_score)。"
    "另外提供：一段總評(summary)、優點清單(strengths)、問題清單(issues，每項含 severity=high/medium/low、"
    "area 所在區塊、problem 問題、fix 可照做的具體修正)、以及 2-4 個改寫前後對照範例(rewrite_examples)。"
    "務實具體、不空泛，不要捏造未提供的經歷。全程使用繁體中文。"
)


def structure_profile(resume_text: str) -> Profile:
    """履歷全文 → 結構化 Profile（cheap 分層）。"""
    llm = get_llm("cheap").with_structured_output(Profile)
    profile = llm.invoke([("system", STRUCTURE_SYSTEM), ("human", resume_text)])
    if not profile.raw_text:
        profile.raw_text = resume_text
    return profile


def evaluate_resume(resume_text: str, profile: Profile) -> ResumeAssessment:
    """履歷健檢評分（deep 分層）。

    健檢報告欄位多（含巢狀 issues/rewrite_examples），且 deep 為推理模型會額外
    消耗 reasoning tokens，故提高 max_tokens 避免結構化輸出被截斷而無法解析。
    """
    llm = get_llm("deep", max_tokens=6000).with_structured_output(ResumeAssessment)
    human = (
        f"【履歷全文】\n{resume_text}\n\n"
        f"【已結構化資料】\n{profile.model_dump_json(indent=2)}"
    )
    return llm.invoke([("system", EVAL_SYSTEM), ("human", human)])
