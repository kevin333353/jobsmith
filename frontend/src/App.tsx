import { useState } from "react"
import type { Seed, UserProfile } from "./types"
import { JobSearchView } from "./views/JobSearchView"
import { ResumeHealthView } from "./views/ResumeHealthView"
import { PipelineView } from "./views/PipelineView"
import { InterviewView } from "./views/InterviewView"
import { BackendSelector } from "./components/BackendSelector"
import { Sidebar } from "./ui/Sidebar"
import type { NavItem } from "./ui/Sidebar"
import { Compass, FileChartColumn, Workflow, MessagesSquare } from "./ui/icons"

type Tab = "search" | "resume" | "pipeline" | "interview"

const NAV: NavItem<Tab>[] = [
  { id: "search", label: "自動找職缺", icon: Compass },
  { id: "resume", label: "履歷健檢", icon: FileChartColumn },
  { id: "pipeline", label: "投遞包工作台", icon: Workflow },
  { id: "interview", label: "面試模擬", icon: MessagesSquare },
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
    <div className="min-h-screen flex">
      <Sidebar items={NAV} active={tab} onSelect={setTab} />
      <div className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          <header className="mb-6 flex items-center justify-end">
            <BackendSelector />
          </header>

          {/* 分頁全掛載只切顯示，保留狀態（職缺清單／投遞包成品） */}
          <div className={tab === "search" ? "" : "hidden"}>
            <JobSearchView onPick={pickJob} onProfile={setProfile} />
          </div>
          <div className={tab === "resume" ? "" : "hidden"}>
            <ResumeHealthView onProfile={setProfile} />
          </div>
          <div className={tab === "pipeline" ? "" : "hidden"}>
            <PipelineView seed={seed} fallbackProfile={profile} onBack={() => setTab("search")} />
          </div>
          <div className={tab === "interview" ? "" : "hidden"}>
            <InterviewView fallbackProfile={profile} />
          </div>
        </div>
      </div>
    </div>
  )
}
