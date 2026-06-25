import { useEffect, useState } from "react"
import type { CandidateProfile, Seed, UserProfile, Preferences } from "./types"
import { JobSearchView } from "./views/JobSearchView"
import { ResumeHealthView } from "./views/ResumeHealthView"
import { PipelineView } from "./views/PipelineView"
import { InterviewView } from "./views/InterviewView"
import { HistoryView } from "./views/HistoryView"
import { SearchHistoryView } from "./views/SearchHistoryView"
import { PreferencesView } from "./views/PreferencesView"
import { BackendSelector } from "./components/BackendSelector"
import { GithubStar } from "./components/GithubStar"
import { Onboarding } from "./components/Onboarding"
import { FirstRunGuide } from "./components/FirstRunGuide"
import {
  loadCandidateProfiles, makeCandidateProfile, profileDisplayName,
  saveCandidateProfiles, upsertCandidateProfile,
} from "./lib/profiles"
import { Sidebar } from "./ui/Sidebar"
import type { NavItem } from "./ui/Sidebar"
import { Button } from "./ui/Button"
import { Compass, FileChartColumn, Workflow, MessagesSquare, Archive, Settings2, Search, ChevronUp, ChevronDown } from "./ui/icons"

type Tab = "search" | "searches" | "resume" | "pipeline" | "interview" | "history" | "settings"

const NAV: NavItem<Tab>[] = [
  { id: "search", label: "自動找職缺", icon: Compass },
  { id: "searches", label: "搜尋紀錄", icon: Search },
  { id: "history", label: "我的投遞包", icon: Archive },
  { id: "pipeline", label: "投遞包工作台", icon: Workflow },
  { id: "interview", label: "面試模擬", icon: MessagesSquare },
  { id: "resume", label: "履歷健檢", icon: FileChartColumn },
]
const FOOTER: NavItem<Tab>[] = [{ id: "settings", label: "個人化", icon: Settings2 }]
const BACKEND_CONFIRMED_KEY = "copilot.backend.confirmed"
const GUIDE_DISMISSED_KEY = "copilot.firstRunGuide.dismissed"

export default function App() {
  const [tab, setTab] = useState<Tab>("search")
  const [backendConfirmed, setBackendConfirmed] = useState(
    () => localStorage.getItem(BACKEND_CONFIRMED_KEY) === "1")
  const [seed, setSeed] = useState<Seed | null>(null)
  const [interviewSeed, setInterviewSeed] = useState<Seed | null>(null)
  // 從「我的投遞包」點進行中的那筆 → 工作台接回該背景產生看即時進度。
  const [watch, setWatch] = useState<{ threadId: string; packageId: number; title?: string; nonce: number } | null>(null)
  // 自動找職缺的搜尋表單收合狀態提升到這裡，讓收合鈕放右上角（選擇模型左側）。
  const [searchFormOpen, setSearchFormOpen] = useState(true)
  const [searchHasResults, setSearchHasResults] = useState(false)
  // 目前 session 明確選用的候選人 Profile；重新開 app 後不自動沿用，避免拿錯人的履歷產出。
  const [activeProfile, setActiveProfile] = useState<CandidateProfile | null>(null)
  const [profiles, setProfiles] = useState<CandidateProfile[]>(() => loadCandidateProfiles())
  const [preferences, setPreferences] = useState<Preferences>({})
  const [privacyVersion, setPrivacyVersion] = useState(0)
  const [guideDismissed, setGuideDismissed] = useState(
    () => localStorage.getItem(GUIDE_DISMISSED_KEY) === "1")
  // 開場引導：第一次使用先選 AI 後端並測試連線；確認過後記在 localStorage 不再跳出。
  const [showOnboard, setShowOnboard] = useState(() => !backendConfirmed)

  // 開 app 載入記憶：偏好自動套用；後端舊版保存的履歷只放進可選 Profile 清單，不設為目前使用。
  useEffect(() => {
    fetch("/api/memory")
      .then((r) => r.json())
      .then((d) => {
        if (d.profile) {
          const profile = d.profile as UserProfile
          setProfiles((ps) => upsertCandidateProfile(ps, makeCandidateProfile(profile, {
            id: "memory-profile",
            label: profileDisplayName(profile),
            resumeLabel: "已儲存履歷",
            saved: true,
          })))
        }
        if (d.preferences) setPreferences(d.preferences as Preferences)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    saveCandidateProfiles(profiles)
  }, [profiles])

  function activateSessionProfile(profile: UserProfile, meta?: { label?: string; resumeLabel?: string }) {
    const candidate = makeCandidateProfile(profile, {
      label: meta?.label || profileDisplayName(profile),
      resumeLabel: meta?.resumeLabel || "本次上傳履歷",
      saved: false,
    })
    setActiveProfile(candidate)
    return candidate
  }

  function selectProfile(profile: CandidateProfile | null) {
    setActiveProfile(profile ? { ...profile, saved: true } : null)
  }

  async function saveActiveProfile(label?: string) {
    if (!activeProfile) return
    const saved: CandidateProfile = {
      ...activeProfile,
      label: (label || activeProfile.label).trim() || profileDisplayName(activeProfile.profile),
      preferences,
      saved: true,
      updatedAt: new Date().toISOString(),
    }
    setProfiles((ps) => upsertCandidateProfile(ps, saved))
    setActiveProfile(saved)
    try {
      await fetch("/api/memory/profile", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: saved.profile }),
      })
    } catch { /* 本機 Profile 已儲存，後端備份失敗不阻斷使用 */ }
  }

  function deleteProfile(id: string) {
    setProfiles((ps) => ps.filter((p) => p.id !== id))
    if (activeProfile?.id === id) setActiveProfile(null)
    fetch("/api/memory/profile", { method: "DELETE" }).catch(() => {})
  }

  function pickJob(jd: string, picked?: UserProfile | null) {
    const nextProfile = picked ?? activeProfile?.profile ?? null
    if (picked) activateSessionProfile(picked, { resumeLabel: "搜尋紀錄履歷" })
    setSeed({ jd, profile: nextProfile, nonce: Date.now() })
    setTab("pipeline")
  }

  // 從「我的投遞包」用該份 JD + 履歷直接開面試模擬。
  function startInterview(jd: string, picked?: UserProfile | null) {
    const nextProfile = picked ?? activeProfile?.profile ?? null
    if (picked) activateSessionProfile(picked, { resumeLabel: "投遞包履歷" })
    setInterviewSeed({ jd, profile: nextProfile, nonce: Date.now() })
    setTab("interview")
  }

  // 點「我的投遞包」進行中的那筆 → 切到工作台、接回該背景產生看進度。
  function watchRun(threadId: string, packageId: number, title?: string) {
    setWatch({ threadId, packageId, title, nonce: Date.now() })
    setTab("pipeline")
  }

  function finishOnboard() {
    localStorage.setItem(BACKEND_CONFIRMED_KEY, "1")
    setBackendConfirmed(true)
    setShowOnboard(false)
  }

  function skipOnboard() {
    setShowOnboard(false)
  }

  function dismissGuide() {
    localStorage.setItem(GUIDE_DISMISSED_KEY, "1")
    setGuideDismissed(true)
  }

  function openBackendOnboarding() {
    setShowOnboard(true)
  }

  function clearPersonalState() {
    setActiveProfile(null)
    setProfiles([])
    setPreferences({})
    setSeed(null)
    setInterviewSeed(null)
    setWatch(null)
    setGuideDismissed(false)
    localStorage.removeItem(GUIDE_DISMISSED_KEY)
    setPrivacyVersion((v) => v + 1)
  }

  const showFirstRunGuide = !showOnboard && !guideDismissed

  return (
    <div className="min-h-screen flex">
      {showOnboard && <Onboarding onDone={finishOnboard} onSkip={skipOnboard} />}
      {showFirstRunGuide && (
        <FirstRunGuide
          backendReady={backendConfirmed}
          onBackend={openBackendOnboarding}
          onStart={() => setTab("search")}
          onDone={dismissGuide}
        />
      )}
      <Sidebar items={NAV} active={tab} onSelect={setTab} footer={FOOTER} />
      <div className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          {/* 投遞包工作台要乾淨一頁式：不顯示右上角的執行模式/模型選擇，內容因此往上移。
              其餘分頁仍保留右上角的後端控制台。 */}
          {tab !== "pipeline" && (
            <header className="mb-6 flex items-center justify-end gap-3">
              {tab === "search" && searchHasResults && (
                <Button variant="secondary" size="sm" icon={searchFormOpen ? ChevronUp : ChevronDown}
                  onClick={() => setSearchFormOpen((o) => !o)}>
                  {searchFormOpen ? "收合搜尋條件" : "修改搜尋條件"}
                </Button>
              )}
              <GithubStar />
              <BackendSelector />
            </header>
          )}

          {/* 分頁全掛載只切顯示，保留狀態 */}
          <div key={`search-${privacyVersion}`} className={tab === "search" ? "" : "hidden"}>
            <JobSearchView onPick={pickJob} onProfile={activateSessionProfile}
              formOpen={searchFormOpen} setFormOpen={setSearchFormOpen} onHasResults={setSearchHasResults} />
          </div>
          <div key={`searches-${privacyVersion}`} className={tab === "searches" ? "" : "hidden"}>
            <SearchHistoryView active={tab === "searches"} onPick={pickJob} />
          </div>
          <div key={`resume-${privacyVersion}`} className={tab === "resume" ? "" : "hidden"}>
            <ResumeHealthView onProfile={activateSessionProfile} />
          </div>
          <div key={`pipeline-${privacyVersion}`} className={tab === "pipeline" ? "" : "hidden"}>
            <PipelineView seed={seed} activeProfile={activeProfile} profiles={profiles}
              preferences={preferences} watch={watch} onBack={() => setTab("search")}
              onSelectProfile={selectProfile} onSaveActiveProfile={saveActiveProfile}
              onDeleteProfile={deleteProfile} onClearActiveProfile={() => setActiveProfile(null)} />
          </div>
          <div key={`interview-${privacyVersion}`} className={tab === "interview" ? "" : "hidden"}>
            <InterviewView active={tab === "interview"} activeProfile={activeProfile} seed={interviewSeed} />
          </div>
          <div key={`history-${privacyVersion}`} className={tab === "history" ? "" : "hidden"}>
            <HistoryView active={tab === "history"} onReopen={pickJob} onInterview={startInterview} onWatch={watchRun} />
          </div>
          <div className={tab === "settings" ? "" : "hidden"}>
            <PreferencesView value={preferences} onSave={setPreferences} onClearData={clearPersonalState}
              profiles={profiles} activeProfile={activeProfile} onSelectProfile={selectProfile}
              onSaveActiveProfile={saveActiveProfile} onDeleteProfile={deleteProfile}
              onClearActiveProfile={() => setActiveProfile(null)} />
          </div>
        </div>
      </div>
    </div>
  )
}
