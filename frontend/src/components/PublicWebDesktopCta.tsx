import { Download, Sparkles } from "../ui/icons"

const LATEST_RELEASE_URL = "https://github.com/kevin333353/jobsmith/releases/latest"

export function PublicWebDesktopCta() {
  return (
    <aside
      aria-label="Jobsmith 桌面完整版"
      className="mx-auto max-w-5xl px-3 pt-3 sm:px-6"
    >
      <div className="flex items-center gap-2.5 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2.5 text-brand-950">
        <Sparkles className="hidden h-4 w-4 shrink-0 text-brand-600 sm:block" />
        <p className="min-w-0 flex-1 text-xs leading-5 sm:text-sm">
          <span className="font-semibold">需要完整 AI 功能？</span>
          {" "}AI 履歷分析、客製履歷與投遞包都在桌面版。
        </p>
        <a
          href={LATEST_RELEASE_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-brand-300 bg-white px-2.5 py-2 text-xs font-semibold text-brand-700 transition hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 sm:px-3 sm:py-1.5 sm:text-sm"
        >
          <Download className="h-4 w-4" />
          <span className="hidden sm:inline">下載桌面版</span>
          <span className="sm:hidden">查看</span>
        </a>
      </div>
    </aside>
  )
}
