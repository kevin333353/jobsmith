import { useEffect, useState } from "react"
import { Star } from "../ui/icons"

const REPO = "kevin333353/jobsmith"
const REPO_URL = "https://github.com/" + REPO

function fmt(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "K"
  return String(n)
}

// 右上角的 GitHub Star CTA：顯示即時 star 數，滑鼠移入顯示提示，點擊到 repo 點 star。
export function GithubStar() {
  const [stars, setStars] = useState<number | null>(null)

  useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && typeof d.stargazers_count === "number") setStars(d.stargazers_count) })
      .catch(() => { /* 離線/被限流就只顯示 Star，不顯示數字 */ })
  }, [])

  return (
    <div className="group/star relative">
      <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label="在 GitHub 為我們點亮 Star"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
        <Star className="w-4 h-4 text-amber-500" />
        Star
        {stars !== null && <span className="text-slate-400">· {fmt(stars)}</span>}
      </a>
      <span role="tooltip"
        className="pointer-events-none absolute top-full right-0 mt-1.5 z-50 whitespace-nowrap rounded-md
          bg-slate-900 text-white text-xs font-medium px-2.5 py-1 shadow-lg opacity-0 transition duration-150
          group-hover/star:opacity-100 group-focus-within/star:opacity-100">
        在 GitHub 為我們點亮 Star
      </span>
    </div>
  )
}
