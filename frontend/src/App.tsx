import { useState } from "react"
import type { ReactNode } from "react"
import type { Seed } from "./types"
import { JobSearchView } from "./views/JobSearchView"
import { ResumeHealthView } from "./views/ResumeHealthView"
import { PipelineView } from "./views/PipelineView"

type Tab = "search" | "resume" | "pipeline"

export default function App() {
  const [tab, setTab] = useState<Tab>("search")
  const [seed, setSeed] = useState<Seed | null>(null)

  function pickJob(jd: string) {
    setSeed({ jd, nonce: Date.now() })
    setTab("pipeline")
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <div className="max-w-6xl mx-auto p-6">
        <header className="mb-5">
          <h1 className="text-2xl font-bold">台灣 AI 求職 Co-pilot</h1>
          <p className="text-slate-500">丟履歷 → 自動找職缺 → 多 agent 產生投遞包</p>
        </header>
        <nav className="no-print flex gap-2 mb-6 border-b">
          <TabBtn active={tab === "search"} onClick={() => setTab("search")}>自動找職缺</TabBtn>
          <TabBtn active={tab === "resume"} onClick={() => setTab("resume")}>履歷健檢</TabBtn>
          <TabBtn active={tab === "pipeline"} onClick={() => setTab("pipeline")}>投遞包工作台</TabBtn>
        </nav>
        {tab === "search" && <JobSearchView onPick={pickJob} />}
        {tab === "resume" && <ResumeHealthView />}
        {tab === "pipeline" && <PipelineView seed={seed} />}
      </div>
    </div>
  )
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm -mb-px border-b-2 ${
        active ? "border-indigo-600 text-indigo-600 font-medium" : "border-transparent text-slate-500"
      }`}
    >
      {children}
    </button>
  )
}
