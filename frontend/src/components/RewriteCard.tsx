import type { ResumeRewrite } from "../types"

export function RewriteCard({ rw }: { rw: ResumeRewrite }) {
  return (
    <div className="border rounded-lg p-4 bg-white space-y-2">
      <div className="text-sm">
        <span className="text-rose-600 font-medium">原句：</span>
        <span className="line-through text-slate-500">{rw.original}</span>
      </div>
      <div className="text-sm">
        <span className="text-emerald-600 font-medium">改寫：</span>
        <span className="text-slate-800">{rw.improved}</span>
      </div>
      <div className="text-xs text-slate-500">原因：{rw.why}</div>
    </div>
  )
}
