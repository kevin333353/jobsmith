import type { ReactNode } from "react"

// 全 app 卡片容器：白底、xl2 圓角、card 陰影；interactive 時 hover 抬升。
export function Card(
  { children, className = "", interactive = false }:
  { children: ReactNode; className?: string; interactive?: boolean },
) {
  return (
    <div
      className={`bg-white border border-slate-200/70 rounded-xl2 shadow-card ${
        interactive ? "transition duration-200 hover:shadow-cardHover hover:-translate-y-0.5" : ""
      } ${className}`}
    >
      {children}
    </div>
  )
}
