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
