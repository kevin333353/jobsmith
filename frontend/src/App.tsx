import { useState } from "react"
import type { ComponentType } from "react"
import type { Seed, UserProfile } from "./types"
import { JobSearchView } from "./views/JobSearchView"
import { ResumeHealthView } from "./views/ResumeHealthView"
import { PipelineView } from "./views/PipelineView"
import { BackendSelector } from "./components/BackendSelector"
import { Brand } from "./ui/Brand"
import { Search, Gauge, Network } from "./ui/icons"

type Tab = "search" | "resume" | "pipeline"

const TABS: { id: Tab; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { id: "search", label: "自動找職缺", icon: Search },
  { id: "resume", label: "履歷健檢", icon: Gauge },
  { id: "pipeline", label: "投遞包工作台", icon: Network },
]

export default function App() {
  const [tab, setTab] = useState<Tab>("search")
  const [seed, setSeed] = useState<Seed | null>(null)
  // 使用者真實履歷（自動找職缺解析後共用），讓「投遞包工作台」分頁手動開跑也能用本人背景。
  const [profile, setProfile] = useState<UserProfile | null>(null)

  function pickJob(jd: string, picked?: UserProfile | null) {
    if (picked) setProfile(picked)
    setSeed({ jd, profile: picked ?? profile, nonce: Date.now() })
    setTab("pipeline")
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        <header className="mb-6 flex items-center justify-between gap-4">
          <Brand />
          <BackendSelector />
        </header>

        <nav className="no-print inline-flex flex-wrap gap-1 p-1 bg-white border border-slate-200 rounded-xl shadow-card mb-6">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`inline-flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition ${
                tab === id
                  ? "bg-brand-600 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </nav>

        {/* 三個分頁都保持掛載，只切換顯示，避免切分頁時遺失狀態（職缺清單／投遞包成品） */}
        <div className={tab === "search" ? "" : "hidden"}>
          <JobSearchView onPick={pickJob} onProfile={setProfile} />
        </div>
        <div className={tab === "resume" ? "" : "hidden"}>
          <ResumeHealthView onProfile={setProfile} />
        </div>
        <div className={tab === "pipeline" ? "" : "hidden"}>
          <PipelineView seed={seed} fallbackProfile={profile} onBack={() => setTab("search")} />
        </div>
      </div>
    </div>
  )
}
