import { useEffect, useState } from "react"
import { Sparkles, Download, X } from "../ui/icons"

type UpdateInfo = { current: string; latest: string | null; update_available: boolean; url: string }

const DISMISS_KEY = "jobsmith.update.dismissed"

// 啟動時問後端有沒有新版（後端只連 GitHub 公開 releases API 比對版本，不送任何使用者資料）。
// 有新版才顯示；使用者關掉某個版本後，同版本不再提醒，之後出更新版會再跳。
export function UpdateBanner() {
  const [info, setInfo] = useState<UpdateInfo | null>(null)

  useEffect(() => {
    fetch("/api/update-check")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: UpdateInfo | null) => {
        if (!d || !d.update_available || !d.latest) return
        if (localStorage.getItem(DISMISS_KEY) === d.latest) return
        setInfo(d)
      })
      .catch(() => { /* 離線/限流就不顯示 */ })
  }, [])

  if (!info) return null

  function dismiss() {
    if (info?.latest) localStorage.setItem(DISMISS_KEY, info.latest)
    setInfo(null)
  }

  return (
    <div className="mb-4 flex items-center gap-3 rounded-xl border border-brand-200 bg-brand-50 px-4 py-2.5 text-sm text-brand-900">
      <Sparkles className="w-4 h-4 shrink-0 text-brand-600" />
      <span className="min-w-0 flex-1">
        有新版 <b>{info.latest}</b> 可用（你目前 v{info.current}）。建議更新以取得最新修正與功能。
      </span>
      <a
        href={info.url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-brand-300 bg-white px-3 py-1.5 font-medium text-brand-700 transition hover:bg-brand-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
      >
        <Download className="w-4 h-4" />前往下載
      </a>
      <button
        type="button"
        onClick={dismiss}
        aria-label="關閉更新提示"
        className="shrink-0 rounded-lg p-1.5 text-brand-400 transition hover:bg-brand-100 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
