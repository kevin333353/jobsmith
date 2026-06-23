import type { ResumeAssessment } from "../types"
import { ScoreRing } from "./ScoreRing"
import { ScoreBars } from "./ScoreBars"
import { IssueCard } from "./IssueCard"
import { RewriteCard } from "./RewriteCard"

export function Dashboard({ a }: { a: ResumeAssessment }) {
  return (
    <div className="space-y-6">
      <div className="grid md:grid-cols-2 gap-6 items-center bg-white border rounded-xl p-6">
        <div className="flex items-center gap-6">
          <ScoreRing score={a.overall_score} />
          <div>
            <h2 className="text-lg font-bold mb-1">履歷健檢總分</h2>
            <p className="text-sm text-slate-600">{a.summary}</p>
          </div>
        </div>
        <ScoreBars scores={a as unknown as Record<string, number>} />
      </div>

      {a.strengths.length > 0 && (
        <section>
          <h3 className="font-semibold mb-2">✅ 優點</h3>
          <div className="grid md:grid-cols-2 gap-2">
            {a.strengths.map((s, i) => (
              <div key={i} className="text-sm bg-emerald-50 border border-emerald-100 rounded-lg p-3">{s}</div>
            ))}
          </div>
        </section>
      )}

      {a.issues.length > 0 && (
        <section>
          <h3 className="font-semibold mb-2">⚠️ 可改進項目</h3>
          <div className="grid md:grid-cols-2 gap-3">
            {a.issues.map((it, i) => <IssueCard key={i} issue={it} />)}
          </div>
        </section>
      )}

      {a.rewrite_examples.length > 0 && (
        <section>
          <h3 className="font-semibold mb-2">✍️ 改寫範例</h3>
          <div className="grid md:grid-cols-2 gap-3">
            {a.rewrite_examples.map((rw, i) => <RewriteCard key={i} rw={rw} />)}
          </div>
        </section>
      )}
    </div>
  )
}
