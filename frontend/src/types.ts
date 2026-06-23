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
  sources: string[]; data_limited: boolean;
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
export interface Seed { jd: string; nonce: number }
