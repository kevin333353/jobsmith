import { useEffect, useState } from "react"
import type { Preferences } from "../types"
import { Card } from "../ui/Card"
import { Button } from "../ui/Button"
import { Settings2, CheckCircle2 } from "../ui/icons"

const TONES = ["自信專業", "務實低調", "親切熱忱", "簡潔有力"]

function split(s: string): string[] {
  return s.split(/[,，]/).map((x) => x.trim()).filter(Boolean)
}

export function PreferencesView(
  { value, onSave }: { value: Preferences; onSave: (p: Preferences) => void },
) {
  const [titles, setTitles] = useState((value.target_titles || []).join("、"))
  const [seniority, setSeniority] = useState(value.seniority || "")
  const [tone, setTone] = useState(value.tone || "")
  const [skills, setSkills] = useState((value.emphasize_skills || []).join("、"))
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)

  // 記憶是非同步載入的：value 由 {} 變成已存偏好時，把欄位同步回填，
  // 否則開「個人化」分頁會看到空白表單（甚至誤存空值蓋掉既有偏好）。
  // 這是「prop 改變時同步本地草稿」的刻意用法。
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTitles((value.target_titles || []).join("、"))
    setSeniority(value.seniority || "")
    setTone(value.tone || "")
    setSkills((value.emphasize_skills || []).join("、"))
  }, [value])

  async function save() {
    setBusy(true); setSaved(false)
    const prefs: Preferences = {
      target_titles: split(titles), seniority: seniority.trim(),
      tone: tone.trim(), emphasize_skills: split(skills),
    }
    try {
      const r = await fetch("/api/memory", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferences: prefs }),
      })
      if (r.ok) { onSave(prefs); setSaved(true) }
    } finally { setBusy(false) }
  }

  const field = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
  return (
    <div className="max-w-2xl">
      <h2 className="font-semibold mb-1 flex items-center gap-2">
        <Settings2 className="w-5 h-5 text-brand-600" />個人化偏好
      </h2>
      <p className="text-sm text-slate-500 mb-4">這些偏好會套用到客製履歷、求職信與面試準備，讓產出更貼近你的方向。</p>
      <Card className="p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">目標職稱（可多個，用、或逗號分隔）</label>
          <input className={field} value={titles} onChange={(e) => setTitles(e.target.value)}
            placeholder="例：AI 工程師、後端工程師" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">目標層級 / 年資</label>
          <input className={field} value={seniority} onChange={(e) => setSeniority(e.target.value)}
            placeholder="例：資深、3-5 年" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">語氣</label>
          <div className="flex flex-wrap gap-2" role="group" aria-label="語氣">
            {TONES.map((t) => (
              <button key={t} type="button" onClick={() => setTone(t)} aria-pressed={tone === t}
                className={`px-3 py-1.5 rounded-lg text-sm border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                  tone === t ? "bg-brand-600 text-white border-brand-600" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}>{t}</button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">想強調的技能（可多個）</label>
          <input className={field} value={skills} onChange={(e) => setSkills(e.target.value)}
            placeholder="例：LLM、LangGraph、RAG" />
        </div>
        <div className="flex items-center gap-3 pt-1">
          <Button onClick={save} loading={busy} icon={CheckCircle2}>儲存偏好</Button>
          {saved && <span className="text-sm text-emerald-600 inline-flex items-center gap-1"><CheckCircle2 className="w-4 h-4" />已儲存</span>}
        </div>
      </Card>
    </div>
  )
}
