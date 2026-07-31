import { useEffect, useState } from "react"
import type { CandidateProfile, JobMatch, Seed, UserProfile, Preferences } from "./types"
import { JobSearchView } from "./views/JobSearchView"
import { ResumeHealthView } from "./views/ResumeHealthView"
import { ResumeCheckHistoryView } from "./views/ResumeCheckHistoryView"
import { PipelineView } from "./views/PipelineView"
import { InterviewView } from "./views/InterviewView"
import { HistoryView } from "./views/HistoryView"
import { SearchHistoryView } from "./views/SearchHistoryView"
import { PreferencesView } from "./views/PreferencesView"
import { BackendSelector } from "./components/BackendSelector"
import { GithubStar } from "./components/GithubStar"
import { PublicWebDesktopCta } from "./components/PublicWebDesktopCta"
import { UpdateBanner } from "./components/UpdateBanner"
import { Onboarding } from "./components/Onboarding"
import { FirstRunGuide } from "./components/FirstRunGuide"
import {
  loadCandidateProfiles, makeCandidateProfile, profileDisplayName,
  saveCandidateProfiles, upsertCandidateProfile,
} from "./lib/profiles"
import { Sidebar } from "./ui/Sidebar"
import type { NavItem } from "./ui/Sidebar"
import { Button } from "./ui/Button"
import { Compass, FileChartColumn, Workflow, MessagesSquare, Archive, Settings2, Search, ChevronUp, ChevronDown, ClipboardList, ShieldCheck } from "./ui/icons"

type Tab = "search" | "searches" | "resume" | "resumeChecks" | "pipeline" | "interview" | "history" | "settings"

const NAV: NavItem<Tab>[] = [
  { id: "search", label: "自動找職缺", icon: Compass },
  { id: "searches", label: "搜尋紀錄", icon: Search },
  { id: "history", label: "我的投遞包", icon: Archive },
  { id: "pipeline", label: "投遞包工作台", icon: Workflow },
  { id: "interview", label: "面試模擬", icon: MessagesSquare },
  { id: "resume", label: "履歷健檢", icon: FileChartColumn },
  { id: "resumeChecks", label: "健檢紀錄", icon: ClipboardList },
]
const FOOTER: NavItem<Tab>[] = [{ id: "settings", label: "個人化", icon: Settings2 }]
const BACKEND_CONFIRMED_KEY = "copilot.backend.confirmed"
const ONBOARDING_DONE_KEY = "copilot.onboarding.done"
const GUIDE_DISMISSED_KEY = "copilot.firstRunGuide.dismissed"

export type RuntimeConfig = {
  public_web: boolean
  ai_enabled: boolean
  persistence_enabled: boolean
  max_search_pages: number
  preview_concurrency?: number | null
  search_concurrency?: number | null
  search_queue_capacity?: number | null
  search_cache_ttl_seconds?: number | null
  analytics_enabled?: boolean
  version: string
}

const DESKTOP_RUNTIME: RuntimeConfig = {
  public_web: false,
  ai_enabled: true,
  persistence_enabled: true,
  max_search_pages: 5,
  version: "",
}

export default function App({ runtime = DESKTOP_RUNTIME }: { runtime?: RuntimeConfig }) {
  return runtime.public_web ? <PublicWebApp runtime={runtime} /> : <DesktopApp />
}

function PublicWebApp({ runtime }: { runtime: RuntimeConfig }) {
  const [searchFormOpen, setSearchFormOpen] = useState(true)
  const [searchHasResults, setSearchHasResults] = useState(false)

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200/90 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-3 py-2.5 sm:px-6">
          <img src="/favicon.svg" alt="" className="h-8 w-8 rounded-lg" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-900">Jobsmith Web</span>
              <span className="hidden rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 sm:inline-flex">
                免 AI
              </span>
            </div>
            <p className="hidden text-[11px] text-slate-500 sm:block">
              手機上傳履歷，直接找台灣職缺
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {searchHasResults && (
              <Button
                variant="secondary"
                size="sm"
                icon={searchFormOpen ? ChevronUp : ChevronDown}
                aria-label={searchFormOpen ? "收合搜尋條件" : "修改搜尋條件"}
                title={searchFormOpen ? "收合搜尋條件" : "修改搜尋條件"}
                className="h-10 w-10 shrink-0 whitespace-nowrap !p-0 sm:h-auto sm:w-auto sm:!px-3 sm:!py-1.5"
                onClick={() => setSearchFormOpen((open) => !open)}
              >
                <span className="hidden sm:inline">
                  {searchFormOpen ? "收合" : "修改條件"}
                </span>
              </Button>
            )}
            <GithubStar liveCount={false} />
          </div>
        </div>
      </header>

      <PublicWebDesktopCta />

      <main className="mx-auto max-w-5xl px-3 py-4 sm:px-6 sm:py-6">
        {!searchHasResults && (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-900">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              公開測試版不需帳號、不呼叫 AI，也不把履歷寫入資料庫。
              檔案只在本次請求中解析；搜尋結果只保存在這台裝置的瀏覽器。
              多人同時使用會自動排隊；熱門條件只共用短期職缺快取，不包含履歷內容。
              {runtime.analytics_enabled && (
                <> 網站只記錄匿名流量、成功／失敗與效能區間，不記錄履歷或搜尋內容。</>
              )}
            </p>
          </div>
        )}
        <JobSearchView
          publicWeb
          maxSearchPages={runtime.max_search_pages}
          onPick={() => undefined}
          formOpen={searchFormOpen}
          setFormOpen={setSearchFormOpen}
          onHasResults={setSearchHasResults}
        />
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-8 pt-2 text-center text-xs text-slate-400">
        Jobsmith {runtime.version ? `v${runtime.version} · ` : ""}
        <a
          href="https://github.com/kevin333353/jobsmith/blob/master/docs/PRIVACY.md"
          target="_blank"
          rel="noreferrer"
          className="underline hover:text-slate-600"
        >
          隱私說明
        </a>
      </footer>
    </div>
  )
}

function DesktopApp() {
  const [tab, setTab] = useState<Tab>("search")
  const [backendConfirmed, setBackendConfirmed] = useState(
    () => localStorage.getItem(BACKEND_CONFIRMED_KEY) === "1")
  const [backendRefreshKey, setBackendRefreshKey] = useState(0)
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
  // 開場引導：免 AI 可直接開始；AI 後端只是選配。完成任一路徑後不再強制彈出。
  const [showOnboard, setShowOnboard] = useState(
    () => localStorage.getItem(ONBOARDING_DONE_KEY) !== "1" && !backendConfirmed,
  )

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

  function updateActiveProfile(profile: UserProfile) {
    setActiveProfile((current) => {
      if (!current) return current
      const oldDisplay = profileDisplayName(current.profile)
      const currentLabel = (current.label || "").trim()
      const shouldRefreshLabel = !currentLabel || currentLabel === oldDisplay
      return {
        ...current,
        profile,
        label: shouldRefreshLabel ? profileDisplayName(profile) : current.label,
        saved: false,
        updatedAt: new Date().toISOString(),
      }
    })
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

  function pickJob(jd: string, picked?: UserProfile | null, match?: JobMatch | null) {
    const nextProfile = picked ?? activeProfile?.profile ?? null
    if (picked) activateSessionProfile(picked, { resumeLabel: "搜尋紀錄履歷" })
    setSeed({ jd, profile: nextProfile, match, nonce: Date.now() })
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
    localStorage.setItem(ONBOARDING_DONE_KEY, "1")
    setBackendConfirmed(true)
    setBackendRefreshKey((key) => key + 1)
    setShowOnboard(false)
  }

  function skipOnboard() {
    localStorage.setItem(ONBOARDING_DONE_KEY, "1")
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
          <UpdateBanner />
          {/* 投遞包工作台要乾淨一頁式：不顯示右上角的執行模式/模型選擇，內容因此往上移。
              其餘分頁仍保留右上角的後端控制台。 */}
          {tab !== "pipeline" && (
            <header className="mb-6 flex flex-wrap items-center justify-end gap-2 sm:gap-3">
              {tab === "search" && searchHasResults && (
                <Button variant="secondary" size="sm" icon={searchFormOpen ? ChevronUp : ChevronDown}
                  className="shrink-0 whitespace-nowrap"
                  onClick={() => setSearchFormOpen((o) => !o)}>
                  {searchFormOpen ? "收合搜尋條件" : "修改搜尋條件"}
                </Button>
              )}
              <GithubStar />
              <BackendSelector refreshKey={backendRefreshKey} />
            </header>
          )}

          {/* 分頁全掛載只切顯示，保留狀態 */}
          <div key={`search-${privacyVersion}`} className={tab === "search" ? "" : "hidden"}>
            <JobSearchView onPick={pickJob} onProfile={activateSessionProfile} activeProfile={activeProfile}
              formOpen={searchFormOpen} setFormOpen={setSearchFormOpen} onHasResults={setSearchHasResults} />
          </div>
          <div key={`searches-${privacyVersion}`} className={tab === "searches" ? "" : "hidden"}>
            <SearchHistoryView active={tab === "searches"} onPick={pickJob} />
          </div>
          <div key={`resume-${privacyVersion}`} className={tab === "resume" ? "" : "hidden"}>
            <ResumeHealthView onProfile={activateSessionProfile} />
          </div>
          <div key={`resumeChecks-${privacyVersion}`} className={tab === "resumeChecks" ? "" : "hidden"}>
            <ResumeCheckHistoryView active={tab === "resumeChecks"} onProfile={activateSessionProfile} />
          </div>
          <div key={`pipeline-${privacyVersion}`} className={tab === "pipeline" ? "" : "hidden"}>
            <PipelineView seed={seed} activeProfile={activeProfile} profiles={profiles}
              preferences={preferences} watch={watch} onBack={() => setTab("search")}
              onSelectProfile={selectProfile} onSaveActiveProfile={saveActiveProfile}
              onUpdateActiveProfile={updateActiveProfile}
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
              onUpdateActiveProfile={updateActiveProfile}
              onClearActiveProfile={() => setActiveProfile(null)} />
          </div>
        </div>
      </div>
    </div>
  )
}
