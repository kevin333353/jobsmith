import type { ResumeRewrite } from "../types"
import { Card } from "../ui/Card"
import { ArrowDown } from "../ui/icons"

export function RewriteCard({ rw }: { rw: ResumeRewrite }) {
  return (
    <Card className="p-4 space-y-2">
      <div className="text-sm rounded-lg bg-rose-50 border border-rose-100 px-3 py-2">
        <span className="text-rose-600 font-medium mr-1.5">原句</span>
        <span className="line-through text-slate-500">{rw.original}</span>
      </div>
      <div className="flex justify-center text-slate-300"><ArrowDown className="w-4 h-4" /></div>
      <div className="text-sm rounded-lg bg-emerald-50 border border-emerald-100 px-3 py-2">
        <span className="text-emerald-600 font-medium mr-1.5">改寫</span>
        <span className="text-slate-800">{rw.improved}</span>
      </div>
      <div className="text-xs text-slate-500">原因：{rw.why}</div>
    </Card>
  )
}
