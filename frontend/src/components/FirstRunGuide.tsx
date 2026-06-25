import { useState } from "react"
import { Brand } from "../ui/Brand"
import { Button } from "../ui/Button"
import {
  ArrowLeft, ArrowRight, CheckCircle2, Cpu, ListChecks, Search, Upload, UserRound, Workflow, X,
} from "../ui/icons"

const STEPS = [
  {
    title: "連接 AI 後端",
    body: "Jobsmith 會使用你選擇的 Claude Code、Codex CLI，或 OpenAI 相容端點產生內容。",
    icon: Cpu,
  },
  {
    title: "提供履歷",
    body: "貼上履歷文字或上傳 PDF / DOCX / TXT，系統會解析成這次 session 可用的候選人背景。",
    icon: Upload,
  },
  {
    title: "確認候選人 Profile",
    body: "如果要跨 session 免重傳，可以手動儲存 Profile。產生投遞包前仍會要求確認，避免套錯履歷。",
    icon: UserRound,
  },
  {
    title: "找職缺並產生投遞包",
    body: "從自動找職缺開始，選定職缺後再產生客製履歷、求職信與面試準備內容。",
    icon: Workflow,
  },
]

export function FirstRunGuide(
  {
    backendReady, onBackend, onStart, onDone,
  }: {
    backendReady: boolean
    onBackend: () => void
    onStart: () => void
    onDone: () => void
  },
) {
  const [page, setPage] = useState(0)
  const cur = STEPS[page]
  const Icon = cur.icon
  const last = page === STEPS.length - 1

  function finish(action?: "backend" | "start") {
    onDone()
    if (action === "backend") onBackend()
    if (action === "start") onStart()
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm grid place-items-center p-4">
      <div className="w-full max-w-xl bg-white rounded-xl2 shadow-cardHover p-6 animate-fade-in-up">
        <div className="flex items-start justify-between gap-4 mb-5">
          <Brand />
          <button
            type="button"
            onClick={() => finish()}
            aria-label="關閉使用教學"
            title="關閉"
            className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
          <ListChecks className="w-4 h-4 text-brand-600" />
          第 {page + 1} / {STEPS.length} 步
        </div>

        <div className="grid sm:grid-cols-[4.25rem_1fr] gap-4 items-start">
          <div className="w-16 h-16 rounded-xl bg-brand-50 text-brand-600 grid place-items-center">
            <Icon className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">{cur.title}</h1>
            <p className="text-sm leading-relaxed text-slate-600">{cur.body}</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-4 gap-1.5" aria-label="教學進度">
          {STEPS.map((s, i) => (
            <button
              key={s.title}
              type="button"
              onClick={() => setPage(i)}
              aria-label={`前往第 ${i + 1} 步：${s.title}`}
              className={`h-1.5 rounded-full transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
                i <= page ? "bg-brand-600" : "bg-slate-200"
              }`}
            />
          ))}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            icon={ArrowLeft}
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            上一步
          </Button>

          {!last ? (
            <Button icon={ArrowRight} onClick={() => setPage((p) => Math.min(STEPS.length - 1, p + 1))}>
              下一步
            </Button>
          ) : backendReady ? (
            <Button icon={Search} onClick={() => finish("start")}>開始找職缺</Button>
          ) : (
            <Button icon={Cpu} onClick={() => finish("backend")}>設定 AI 後端</Button>
          )}

          <button
            type="button"
            onClick={() => finish()}
            className="ml-auto text-sm text-slate-400 hover:text-slate-600 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
          >
            不再顯示
          </button>
        </div>

        {backendReady && (
          <p className="text-xs text-emerald-700 mt-3 inline-flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />AI 後端已完成設定
          </p>
        )}
      </div>
    </div>
  )
}
