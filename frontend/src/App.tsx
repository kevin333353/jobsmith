import { useEffect, useState } from "react"
import type { Seed, UserProfile, Preferences } from "./types"
import { JobSearchView } from "./views/JobSearchView"
import { ResumeHealthView } from "./views/ResumeHealthView"
import { PipelineView } from "./views/PipelineView"
import { InterviewView } from "./views/InterviewView"
import { HistoryView } from "./views/HistoryView"
import { PreferencesView } from "./views/PreferencesView"
import { BackendSelector } from "./components/BackendSelector"
import { Sidebar } from "./ui/Sidebar"
import type { NavItem } from "./ui/Sidebar"
import { Compass, FileChartColumn, Workflow, MessagesSquare, Archive, Settings2 } from "./ui/icons"

type Tab = "search" | "resume" | "pipeline" | "interview" | "history" | "settings"

const NAV: NavItem<Tab>[] = [
  { id: "search", label: "自動找職缺", icon: Compass },
  { id: "resume", label: "履歷健檢", icon: FileChartColumn },
  { id: "pipeline", label: "投遞包工作台", icon: Workflow },
  { id: "interview", label: "面試模擬", icon: MessagesSquare },
  { id: "history", label: "我的投遞包", icon: Archive },
]
const FOOTER: NavItem<Tab>[] = [{ id: "settings", label: "個人化", icon: Settings2 }]

export default function App() {
  const [tab, setTab] = useState<Tab>("search")
  const [seed, setSeed] = useState<Seed | null>(null)
  // 使用者真實履歷（自動找職缺解析後共用），讓「投遞包工作台」分頁手動開跑也能用本人背景。
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [preferences, setPreferences] = useState<Preferences>({})

  // 開 app 載入記憶：有最近履歷則自動帶入（免重傳）、套用偏好。
  useEffect(() => {
    fetch("/api/memory")
      .then((r) => r.json())
      .then((d) => {
        if (d.profile) setProfile(d.profile as UserProfile)
        if (d.preferences) setPreferences(d.preferences as Preferences)
      })
      .catch(() => {})
  }, [])

  function pickJob(jd: string, picked?: UserProfile | null) {
    if (picked) setProfile(picked)
    setSeed({ jd, profile: picked ?? profile, nonce: Date.now() })
    setTab("pipeline")
  }

  return (
    <div className="min-h-screen flex">
      <Sidebar items={NAV} active={tab} onSelect={setTab} footer={FOOTER} />
      <div className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          <header className="mb-6 flex items-center justify-end">
            <BackendSelector />
          </header>

          {/* 分頁全掛載只切顯示，保留狀態 */}
          <div className={tab === "search" ? "" : "hidden"}>
            <JobSearchView onPick={pickJob} onProfile={setProfile} />
          </div>
          <div className={tab === "resume" ? "" : "hidden"}>
            <ResumeHealthView onProfile={setProfile} />
          </div>
          <div className={tab === "pipeline" ? "" : "hidden"}>
            <PipelineView seed={seed} fallbackProfile={profile} preferences={preferences} onBack={() => setTab("search")} />
          </div>
          <div className={tab === "interview" ? "" : "hidden"}>
            <InterviewView fallbackProfile={profile} />
          </div>
          <div className={tab === "history" ? "" : "hidden"}>
            <HistoryView active={tab === "history"} onReopen={pickJob} />
          </div>
          <div className={tab === "settings" ? "" : "hidden"}>
            <PreferencesView value={preferences} onSave={setPreferences} />
          </div>
        </div>
      </div>
    </div>
  )
}
