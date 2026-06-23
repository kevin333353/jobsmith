"""共享領域模型（強型別、可被 with_structured_output 使用）。"""
from pydantic import BaseModel, Field


class Profile(BaseModel):
    """使用者求職背景。"""
    name: str
    summary: str = Field(description="一句話自我介紹/定位")
    skills: list[str] = Field(default_factory=list)
    experiences: list[str] = Field(default_factory=list, description="經歷條列")
    education: str | None = None
    years_experience: float | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    raw_text: str = Field(description="原始貼上的履歷文字")


class ParsedJob(BaseModel):
    """解析後的職缺。"""
    title: str
    company: str
    location: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    min_years: float | None = None
    tech_stack: list[str] = Field(default_factory=list)
    language: str = Field(default="zh", description="JD 主要語言: zh 或 en")
    salary: str | None = None


class MatchReport(BaseModel):
    """匹配評分報告。"""
    score: int = Field(ge=0, le=100, description="0-100 匹配分數")
    matched: list[str] = Field(default_factory=list, description="符合的項目")
    gaps: list[str] = Field(default_factory=list, description="落差/缺少的項目")
    suggestions: list[str] = Field(default_factory=list, description="補強建議")
    recommend_proceed: bool = Field(description="是否建議繼續產出投遞包")
    reason: str = Field(description="建議續做與否的理由")


class CompanyBrief(BaseModel):
    """⑧ 公司情報卡。"""
    company: str
    size: str | None = None
    industry: str | None = None
    funding: str | None = Field(default=None, description="資金/募資狀況")
    salary_range: str | None = None
    benefits: list[str] = Field(default_factory=list)
    culture_summary: str | None = None
    interview_reviews: str | None = Field(default=None, description="面試評價摘要")
    red_flags: list[str] = Field(default_factory=list, description="避雷/負評")
    recent_news: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list, description="來源連結")
    data_limited: bool = Field(default=False, description="查無足夠公開資料時為 True")


class TailoredResume(BaseModel):
    """③ 針對單一職缺客製的履歷。"""
    summary: str = Field(description="針對此職缺的定位句")
    bullets: list[str] = Field(default_factory=list, description="改寫後的經歷條列")
    ats_keywords_hit: list[str] = Field(default_factory=list)
    ats_keywords_missing: list[str] = Field(default_factory=list)
    notes: str | None = None


class CoverLetter(BaseModel):
    """④ 求職信/自傳。"""
    subject: str | None = None
    body: str = Field(description="繁中求職信/自傳全文")
    company_facts_used: list[str] = Field(default_factory=list, description="引用的公司事實")


class InterviewKit(BaseModel):
    """⑤ 面試準備包。"""
    technical_questions: list[str] = Field(default_factory=list)
    behavioral_questions: list[str] = Field(default_factory=list)
    taiwan_specific_questions: list[str] = Field(default_factory=list, description="自傳/期望薪資/為什麼想加入等")
    sample_answers: list[str] = Field(default_factory=list, description="STAR 擬答")
    reverse_questions: list[str] = Field(default_factory=list, description="反向提問")
    company_focus_points: list[str] = Field(default_factory=list, description="公司近況考點")
    cautions: list[str] = Field(default_factory=list, description="避雷提醒")


class CritiqueReport(BaseModel):
    """⑥ 品管/反思評審報告。"""
    resume_score: int = Field(ge=0, le=100)
    cover_letter_score: int = Field(ge=0, le=100)
    interview_score: int = Field(ge=0, le=100)
    overall_pass: bool = Field(description="三份成品是否整體達標")
    feedback: list[str] = Field(default_factory=list, description="若未通過，給下一輪的具體修改指示")
