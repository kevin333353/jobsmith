// 載入骨架：底色 + shimmer 掃光。
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden bg-slate-100 rounded-lg ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/70 to-transparent" />
    </div>
  )
}
