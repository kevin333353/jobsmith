// 品牌：節點圖記（多 agent 網路）+ wordmark。
function Logomark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="brandLogo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4f46e5" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#brandLogo)" />
      <path d="M10 22 L16 11 L22 22" fill="none" stroke="white" strokeWidth="2.4"
        strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="10" cy="22" r="2.6" fill="white" />
      <circle cx="16" cy="11" r="2.6" fill="white" />
      <circle cx="22" cy="22" r="2.6" fill="white" />
    </svg>
  )
}

export function Brand({ size = "md" }: { size?: "sm" | "md" }) {
  return (
    <div className="flex items-center gap-3">
      <Logomark size={size === "sm" ? 30 : 40} />
      <div className="leading-tight">
        <div className={`font-display font-bold ${size === "sm" ? "text-base" : "text-xl"}`}>
          <span className="text-slate-900">Job</span><span className="text-brand-600">Copilot</span>
        </div>
        <div className="text-xs text-slate-500">台灣 AI 求職 Co-pilot</div>
      </div>
    </div>
  )
}
