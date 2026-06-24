import type { ReactNode, KeyboardEvent as ReactKeyboardEvent } from "react"

// 全 app 卡片容器：白底、xl2 圓角、card 陰影；interactive 時 hover 抬升。
export function Card(
  { children, className = "", interactive = false, onClick }:
  { children: ReactNode; className?: string; interactive?: boolean; onClick?: () => void },
) {
  // 整張卡即按鈕（interactive + onClick）時，補上鍵盤可達性：可聚焦、Enter/Space 觸發、焦點環。
  const clickable = interactive && !!onClick
  const a11y = clickable
    ? {
        role: "button" as const,
        tabIndex: 0,
        onKeyDown: (e: ReactKeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick?.() }
        },
      }
    : {}
  return (
    <div
      onClick={onClick}
      {...a11y}
      className={`bg-white border border-slate-200/70 rounded-xl2 shadow-card ${
        interactive ? "transition duration-200 hover:shadow-cardHover hover:-translate-y-0.5" : ""
      } ${clickable ? "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300" : ""} ${className}`}
    >
      {children}
    </div>
  )
}
