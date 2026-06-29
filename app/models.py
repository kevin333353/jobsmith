"""共享領域模型（強型別、可被 with_structured_output 使用）。"""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def coerce_str(v):
    """LLM 字串欄位防呆：null → ""；陣列 → 頓號串接。

    不同後端對同一 schema 的輸出形狀不一（claude 多半守規矩；codex/gpt 常把單一字串欄位
    回成 null 或 list，例如 education 給多筆學歷）。先收斂再驗證，避免結構化解析失敗。
    """
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "、".join(str(x).strip() for x in v if x is not None and str(x).strip())
    return v


def coerce_str_list(v):
    """LLM 字串清單欄位防呆：null → []；單一字串 → [字串]。"""
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    return v


class Profile(BaseModel):
    """使用者求職背景。"""
    name: str = ""
    summary: str = Field(default="", description="一句話自我介紹/定位")
    skills: list[str] = Field(default_factory=list)
    experiences: list[str] = Field(default_factory=list, description="經歷條列")
    education: str = ""
    years_experience: float | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    raw_text: str = Field(default="", description="原始貼上的履歷文字")
    parse_degraded: bool = Field(
        default=False,
        description="True 表示 AI 後端解析失敗、改用本機備援（內容可能不準），供前端提示使用者檢查後端。",
    )

    @field_validator("name", "summary", "education", "raw_text", mode="before")
    @classmethod
    def _coerce_strs(cls, v):
        return coerce_str(v)

    @field_validator("skills", "experiences", "preferred_roles", mode="before")
    @classmethod
    def _coerce_lists(cls, v):
        return coerce_str_list(v)

    @field_validator("years_experience", mode="before")
    @classmethod
    def _coerce_years(cls, v):
        # 年資可能被回成 "約 5 年" 這種字串：抽第一個數字，抽不到就 None（而非驗證失敗）。
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        m = re.search(r"\d+(?:\.\d+)?", str(v))
        return float(m.group()) if m else None


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
    note: str | None = Field(default=None, description="降級原因/提醒（如未設搜尋金鑰）")


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
    per_doc: dict[str, list[str]] = Field(
        default_factory=dict,
        description="逐文件具體修改指示，鍵只能是 resume / cover_letter / interview；"
                    "只放『未達標、需重寫』的文件，已達標的文件不要放（用於精準重寫，不重跑已過的文件）。")
    feedback: list[str] = Field(default_factory=list,
                                description="（程式由 per_doc 自動彙整，模型可不填）")


class ResumeIssue(BaseModel):
    """履歷健檢發現的單一問題。"""
    severity: str = Field(description="嚴重度：high | medium | low")
    area: str = Field(description="問題所在區塊，如『工作經歷』『技能』")
    problem: str = Field(description="問題描述")
    fix: str = Field(description="具體可照做的修正建議")


class ResumeRewrite(BaseModel):
    """改寫前後對照範例。"""
    original: str = Field(description="原句")
    improved: str = Field(description="改寫後")
    why: str = Field(description="為何更好")

    @model_validator(mode="before")
    @classmethod
    def _coerce_aliases(cls, data):
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if not out.get("original"):
            out["original"] = out.get("before") or out.get("old") or out.get("source") or ""
        if not out.get("improved"):
            out["improved"] = out.get("after") or out.get("new") or out.get("rewrite") or ""
        if not out.get("why"):
            out["why"] = (
                out.get("reason")
                or out.get("explanation")
                or out.get("rationale")
                or "改寫後更清楚、具體且更貼近目標職缺。"
            )
        return out


class ResumeAssessment(BaseModel):
    """② 履歷健檢報告。"""
    assessment_mode: str = Field(default="deep", description="deep | fallback")
    fallback_reason: str = Field(default="", description="備援健檢原因；深度健檢成功時為空")
    overall_score: int = Field(ge=0, le=100, description="整體分數")
    clarity_score: int = Field(ge=0, le=100, description="表達清晰度")
    impact_score: int = Field(ge=0, le=100, description="量化成果/影響力")
    ats_keyword_score: int = Field(ge=0, le=100, description="ATS 關鍵字涵蓋")
    localization_score: int = Field(ge=0, le=100, description="台灣履歷慣例符合度")
    completeness_score: int = Field(ge=0, le=100, description="完整度")
    summary: str = Field(description="一段總評")
    strengths: list[str] = Field(default_factory=list, description="優點清單")
    issues: list[ResumeIssue] = Field(default_factory=list, description="問題清單")
    rewrite_examples: list[ResumeRewrite] = Field(default_factory=list, description="改寫範例")


class JobPosting(BaseModel):
    """正規化後的單一職缺。"""
    source: str = Field(description="104 | cake | yourator | linkedin | url")
    title: str
    company: str
    location: str | None = None
    salary: str | None = None
    url: str
    snippet: str | None = Field(default=None, description="職缺摘要")
    requirements: list[str] = Field(default_factory=list)
    raw_text: str = Field(default="", description="原始職缺全文，供後續解析")
    experience_text: str | None = Field(default=None, description="來源文字中的年資要求片段")
    min_years: float | None = Field(default=None, description="解析出的最低年資要求")

    @model_validator(mode="after")
    def _infer_experience(self):
        if self.min_years is None and not self.experience_text:
            from app.sources.experience import parse_experience_requirement
            min_years, text = parse_experience_requirement(
                self.title,
                self.snippet,
                " ".join(str(r) for r in self.requirements),
                self.raw_text,
            )
            self.min_years = min_years
            self.experience_text = text
        return self


class JobMatch(BaseModel):
    """職缺對履歷的適配評分。"""
    job: JobPosting
    fit_score: int = Field(ge=0, le=100, description="適配分數")
    matched: list[str] = Field(default_factory=list, description="符合點")
    gaps: list[str] = Field(default_factory=list, description="落差點")
    reason: str = Field(default="", description="為什麼適合/不適合")


class JobPostingList(BaseModel):
    """job 列表的結構化輸出包裝（供 WebSearch 找公司官網職缺）。"""
    items: list[JobPosting] = Field(default_factory=list)


class SearchResult(BaseModel):
    """單一來源的搜尋結果（被擋或錯誤時 blocked=True）。"""
    source: str
    jobs: list[JobPosting] = Field(default_factory=list)
    blocked: bool = Field(default=False)
    error: str | None = None


class SkillCount(BaseModel):
    """技能 + 在搜到職缺中的需求次數。"""
    skill: str
    count: int = 0


class SkillGapReport(BaseModel):
    """技能缺口市場分析（純彙整搜到職缺的 requirements）。"""
    top_demand: list[SkillCount] = Field(default_factory=list, description="市場最常要求的技能")
    your_gaps: list[SkillCount] = Field(default_factory=list, description="你還沒有、但市場在要的技能")
    have: list[str] = Field(default_factory=list, description="你已具備且市場有在要的技能")


class InterviewQuestion(BaseModel):
    """多輪面試模擬的單一題目。"""
    category: str = Field(default="", description="技術 / 行為 / 台灣特有")
    question: str = ""


class InterviewQuestionList(BaseModel):
    """generate_questions 的結構化輸出包裝。"""
    items: list[InterviewQuestion] = Field(default_factory=list)


class AnswerFeedback(BaseModel):
    """對單一作答的即時回饋。"""
    score: int = Field(default=0, ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    sample_answer: str = Field(default="", description="示範答法")


class InterviewSummary(BaseModel):
    """整場面試的總評。"""
    overall_score: int = Field(default=0, ge=0, le=100)
    summary: str = ""
    advice: list[str] = Field(default_factory=list)


class SupervisorDecision(BaseModel):
    """① Supervisor 的調度決策（LLM 動態判斷，取代寫死門檻；失敗時回門檻備援）。"""
    next_action: Literal["proceed", "stop", "revise", "approve"] = Field(
        description="proceed=續做投遞包 / stop=不續做 / revise=重寫 / approve=送人工核可")
    docs_to_revise: list[str] = Field(
        default_factory=list,
        description="next_action=revise 時要重寫哪些文件，鍵限 resume/cover_letter/interview")
    rationale: str = Field(default="", description="決策理由（給使用者看的一句話）")
