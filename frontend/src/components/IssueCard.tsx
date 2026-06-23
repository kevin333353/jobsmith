import type { ResumeIssue } from "../types"

const SEV: Record<string, { label: string; cls: string }> = {
  high: { label: "高", cls: "bg-rose-100 text-rose-700" },
  medium: { label: "中", cls: "bg-amber-100 text-amber-700" },
  low: { label: "低", cls: "bg-slate-100 text-slate-600" },
}

export function IssueCard({ issue }: { issue: ResumeIssue }) {
  const sev = SEV[issue.severity] ?? SEV.low
  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs px-2 py-0.5 rounded-full ${sev.cls}`}>嚴重度：{sev.label}</span>
        <span className="text-sm font-medium text-slate-500">{issue.area}</span>
      </div>
      <p className="text-sm text-slate-800">{issue.problem}</p>
      <p className="text-sm text-emerald-700 mt-1">建議：{issue.fix}</p>
    </div>
  )
}
