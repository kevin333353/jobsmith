import type { SkillGapReport, UserProfile } from "../../types"
import {
  profileRecognition,
  type JobSearchMode,
} from "../../lib/localDiscovery"
import { Badge } from "../../ui/Badge"
import { Card } from "../../ui/Card"
import { Gauge, Target, UserRound } from "../../ui/icons"

export function DiscoveryInsights(
  {
    profile,
    skillGap,
    mode,
  }: {
    profile?: UserProfile | null
    skillGap?: SkillGapReport | null
    mode: JobSearchMode
  },
) {
  const recognition = profileRecognition(profile)
  const have = (skillGap?.have || []).slice(0, 6)
  const gaps = (skillGap?.your_gaps || []).slice(0, 6)
  if (!recognition && !have.length && !gaps.length) return null

  return (
    <Card className="mb-4 overflow-hidden">
      <div className="grid gap-0 md:grid-cols-2 md:divide-x md:divide-slate-200">
        {recognition && (
          <section className="p-4" aria-label="履歷辨識結果">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <UserRound className="h-4 w-4 text-brand-600" />
              <h3 className="text-sm font-semibold text-slate-900">履歷辨識結果</h3>
              <Badge tone={mode === "local" ? "emerald" : "brand"}>
                {mode === "local" ? "本機規則 · 0 AI" : "AI 解析"}
              </Badge>
            </div>
            {(recognition.name || recognition.summary) && (
              <p className="mb-2 text-xs text-slate-500">
                {[recognition.name, recognition.summary].filter(Boolean).join(" · ")}
              </p>
            )}
            <div className="flex flex-wrap gap-1.5">
              {recognition.roles.slice(0, 4).map((role) => (
                <Badge key={role} tone="brand"><Target className="h-3 w-3" />{role}</Badge>
              ))}
              {recognition.yearsExperience !== null && (
                <Badge tone="slate">{recognition.yearsExperience} 年經驗</Badge>
              )}
              {recognition.skills.slice(0, 8).map((skill) => (
                <Badge key={skill} tone="slate">{skill}</Badge>
              ))}
            </div>
            {mode === "local" && (
              <p className="mt-2 text-xs text-slate-400">
                未呼叫生成式 AI；搜尋前請快速確認職稱、技能與年資是否符合履歷。
              </p>
            )}
          </section>
        )}

        {(have.length > 0 || gaps.length > 0) && (
          <section className="p-4" aria-label="市場技能雷達">
            <div className="mb-2 flex items-center gap-2">
              <Gauge className="h-4 w-4 text-amber-600" />
              <h3 className="text-sm font-semibold text-slate-900">市場技能雷達</h3>
              <Badge tone="slate">依目前職缺統計</Badge>
            </div>
            {have.length > 0 && (
              <div className="mb-2 flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-slate-500">你已具備</span>
                {have.map((skill) => <Badge key={skill} tone="emerald">{skill}</Badge>)}
              </div>
            )}
            {gaps.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-slate-500">常見缺口</span>
                {gaps.map((item) => (
                  <Badge key={item.skill} tone="amber">
                    {item.skill} · {item.count} 筆
                  </Badge>
                ))}
              </div>
            )}
            <p className="mt-2 text-xs text-slate-400">
              僅彙整適配職缺中明確出現的技能，不會把未標示項目當成你不具備。
            </p>
          </section>
        )}
      </div>
    </Card>
  )
}
