export interface ResumeIssue { severity: "high" | "medium" | "low"; area: string; problem: string; fix: string }
export interface ResumeRewrite { original: string; improved: string; why: string }
export interface ResumeAssessment {
  assessment_mode?: "deep" | "fallback" | string; fallback_reason?: string;
  overall_score: number; clarity_score: number; impact_score: number;
  ats_keyword_score: number; localization_score: number; completeness_score: number;
  summary: string; strengths: string[]; issues: ResumeIssue[]; rewrite_examples: ResumeRewrite[];
}
export type SSEEvent =
  | { type: "start"; task_id?: string }
  | { type: "progress"; step: string; message: string }
  | { type: "profile"; data: unknown }
  | { type: "saved_check"; id: number }
  | { type: "assessment"; data: ResumeAssessment }
  | { type: "stopped"; message: string }
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
  experience_text?: string | null; min_years?: number | null;
}
export interface JobMatch {
  job: JobPosting; fit_score: number; matched: string[]; gaps: string[]; reason: string;
}
// 使用者真實履歷結構（後端 /api/jobs/auto 與 /api/resume/evaluate 的 profile 事件，已排除 raw_text）
export type UserProfile = Record<string, unknown>

export interface ResumeCheckSummary {
  id: number; created_at: string; label: string; resume_label: string;
  candidate_name: string; overall_score: number; assessment_mode: string; fallback_reason: string;
}
export interface ResumeCheckDetail extends ResumeCheckSummary {
  profile?: UserProfile | null; assessment: ResumeAssessment;
}

export interface EditableProfile {
  name: string;
  summary: string;
  skills: string;
  experiences: string;
  education: string;
  years_experience: string;
  preferred_roles: string;
}

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

// 使用者明確儲存的候選人 Profile；跨 session 只保留清單，不自動設為目前使用。
export interface CandidateProfile {
  id: string;
  label: string;
  profile: UserProfile;
  resumeLabel?: string;
  preferences?: Preferences;
  createdAt: string;
  updatedAt: string;
  saved?: boolean;
}

// 技能缺口市場分析（對應後端 app/agents/skill_gap.py）
export interface SkillCount { skill: string; count: number }
export interface SkillGapReport { top_demand: SkillCount[]; your_gaps: SkillCount[]; have: string[] }

// ---- SSE 事件型別（取代各 view 的 any；對應後端 app/server.py 的串流）----
// /api/jobs/auto：自動找職缺
export type JobsAutoEvent =
  | { type: "start"; task_id?: string }
  | { type: "progress"; step: string; message: string }
  | { type: "profile"; data: UserProfile }
  | { type: "queries"; queries: string[] }
  | { type: "source"; source: string; count: number; blocked: boolean }
  | { type: "all_blocked"; message: string }
  | { type: "rank_start"; total: number; fallback: boolean }
  | { type: "ranked_batch"; data: JobMatch[] }
  | { type: "company_jobs"; data: JobMatch[] }
  | { type: "linkedin"; url: string }
  | { type: "stopped"; message: string }
  | { type: "error"; message: string }
  | { type: "done" }

// /api/run 與 /api/resume：投遞包多 agent pipeline
export type PipelineEvent =
  | { type: "start"; thread_id: string }
  | { type: "node"; node: string; data?: Partial<PipelineState> }
  | { type: "node_error"; node: string; message: string }
  | { type: "profile_warning"; message: string }
  | ({ type: "telemetry" } & TelemetryEntry)
  | { type: "interrupt"; thread_id: string }
  | { type: "stopped"; message: string }
  | { type: "error"; message: string }
  | { type: "done"; package_id?: number }

// 多輪面試模擬（對應後端 app/agents/interview_sim.py）
export interface InterviewQuestion { category: string; question: string }
export interface AnswerFeedback {
  score: number; strengths: string[]; improvements: string[]; sample_answer: string;
}
export interface InterviewSummary { overall_score: number; summary: string; advice: string[] }

// 與 AI 討論修改履歷/求職信時，後端回傳的修訂（對應 /api/pipeline/chat 的 updated）
export interface RefineUpdate { summary?: string; bullets?: string[]; subject?: string; body?: string }

// 投遞包可編輯欄位（履歷 summary/bullets、求職信 subject/body；bullets 以換行分隔）
export interface EditablePackage {
  resumeSummary: string;
  resumeBullets: string;
  coverSubject: string;
  coverBody: string;
}
