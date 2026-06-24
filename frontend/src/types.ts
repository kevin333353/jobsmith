export interface ResumeIssue { severity: "high" | "medium" | "low"; area: string; problem: string; fix: string }
export interface ResumeRewrite { original: string; improved: string; why: string }
export interface ResumeAssessment {
  overall_score: number; clarity_score: number; impact_score: number;
  ats_keyword_score: number; localization_score: number; completeness_score: number;
  summary: string; strengths: string[]; issues: ResumeIssue[]; rewrite_examples: ResumeRewrite[];
}
export type SSEEvent =
  | { type: "start" }
  | { type: "progress"; step: string; message: string }
  | { type: "profile"; data: unknown }
  | { type: "assessment"; data: ResumeAssessment }
  | { type: "done" }
  | { type: "error"; message: string }

// ---- 多 agent 投遞包流程（對應後端 app/models.py）----
export interface ParsedJob {
  title: string; company: string; location?: string | null;
  responsibilities: string[]; required_skills: string[]; nice_to_have: string[];
  min_years?: number | null; tech_stack: string[]; language: string; salary?: string | null;
}
export interface MatchReport {
  score: number; matched: string[]; gaps: string[]; suggestions: string[];
  recommend_proceed: boolean; reason: string;
}
export interface CompanyBrief {
  company: string; size?: string | null; industry?: string | null; funding?: string | null;
  salary_range?: string | null; benefits: string[]; culture_summary?: string | null;
  interview_reviews?: string | null; red_flags: string[]; recent_news: string[];
  sources: string[]; data_limited: boolean; note?: string | null;
}
export interface TailoredResume {
  summary: string; bullets: string[]; ats_keywords_hit: string[];
  ats_keywords_missing: string[]; notes?: string | null;
}
export interface CoverLetter {
  subject?: string | null; body: string; company_facts_used: string[];
}
export interface InterviewKit {
  technical_questions: string[]; behavioral_questions: string[];
  taiwan_specific_questions: string[]; sample_answers: string[];
  reverse_questions: string[]; company_focus_points: string[]; cautions: string[];
}
export interface CritiqueReport {
  resume_score: number; cover_letter_score: number; interview_score: number;
  overall_pass: boolean; feedback: string[];
}
export interface PipelineState {
  parsed_job?: ParsedJob; match_report?: MatchReport; company_brief?: CompanyBrief;
  tailored_resume?: TailoredResume; cover_letter?: CoverLetter; interview_kit?: InterviewKit;
  critique?: CritiqueReport; approved?: boolean | null; revision_count?: number;
}

// ---- 職缺探索（對應 app/models.py 的 JobPosting / JobMatch）----
export interface JobPosting {
  source: string; title: string; company: string; location?: string | null;
  salary?: string | null; url: string; snippet?: string | null; requirements: string[];
}
export interface JobMatch {
  job: JobPosting; fit_score: number; matched: string[]; gaps: string[]; reason: string;
}
// 使用者真實履歷結構（後端 /api/jobs/auto 與 /api/resume/evaluate 的 profile 事件，已排除 raw_text）
export type UserProfile = Record<string, unknown>

// 從職缺列表「產生投遞包」時，帶 JD + 使用者真實履歷進 pipeline（profile 缺省則後端用 demo）
export interface Seed { jd: string; profile?: UserProfile | null; nonce: number }

// 逐節點 agent telemetry（後端 telemetry SSE 事件）
export interface TelemetryEntry {
  node: string; latency_ms: number; calls: number;
  input_tokens: number; output_tokens: number; cost_usd: number;
}

// 個人化偏好（對應後端 user_memory.preferences）
export interface Preferences {
  target_titles?: string[]; seniority?: string; tone?: string; emphasize_skills?: string[];
}

// 技能缺口市場分析（對應後端 app/agents/skill_gap.py）
export interface SkillCount { skill: string; count: number }
export interface SkillGapReport { top_demand: SkillCount[]; your_gaps: SkillCount[]; have: string[] }

// 多輪面試模擬（對應後端 app/agents/interview_sim.py）
export interface InterviewQuestion { category: string; question: string }
export interface AnswerFeedback {
  score: number; strengths: string[]; improvements: string[]; sample_answer: string;
}
export interface InterviewSummary { overall_score: number; summary: string; advice: string[] }

// 投遞包可編輯欄位（履歷 summary/bullets、求職信 subject/body；bullets 以換行分隔）
export interface EditablePackage {
  resumeSummary: string;
  resumeBullets: string;
  coverSubject: string;
  coverBody: string;
}
