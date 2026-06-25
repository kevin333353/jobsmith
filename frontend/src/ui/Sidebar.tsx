import type { ComponentType } from "react"
import { Logomark } from "./Brand"

export interface NavItem<T extends string = string> {
  id: T
  label: string
  icon: ComponentType<{ className?: string }>
}

// 左側 rail：固定窄軌（只露 logo + 圖示），不展開；滑鼠移到某圖示時，
// 在它右邊冒出該工具名稱的 tooltip。主畫面因此一直保有最大空間。
export function Sidebar<T extends string>(
  { items, active, onSelect, footer }:
  { items: NavItem<T>[]; active: T; onSelect: (id: T) => void; footer?: NavItem<T>[] },
) {
  const renderItem = ({ id, label, icon: Icon }: NavItem<T>) => (
    <div key={id} className="group/item relative flex justify-center">
      <button
        onClick={() => onSelect(id)}
        aria-label={label}
        aria-current={active === id ? "page" : undefined}
        className={`flex items-center justify-center w-11 h-11 my-1 rounded-xl transition
          focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 ${
          active === id
            ? "bg-brand-50 text-brand-600 ring-1 ring-brand-100"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
      >
        <Icon className="w-5 h-5" />
      </button>
      {/* 滑鼠移入才顯示的工具名稱提示（在圖示右邊） */}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 z-50
          whitespace-nowrap rounded-md bg-slate-900 text-white text-xs font-medium px-2.5 py-1 shadow-lg
          opacity-0 -translate-x-1 transition duration-150
          group-hover/item:opacity-100 group-hover/item:translate-x-0
          group-focus-within/item:opacity-100 group-focus-within/item:translate-x-0"
      >
        {label}
      </span>
    </div>
  )

  return (
    <aside className="no-print shrink-0 w-16 border-r border-slate-200 bg-white/80 backdrop-blur
      flex flex-col items-center sticky top-0 h-screen z-30">
      <div className="h-16 flex items-center justify-center shrink-0">
        <Logomark size={30} />
      </div>
      <nav className="flex-1 w-full flex flex-col items-center py-2">{items.map(renderItem)}</nav>
      {footer && footer.length > 0 && (
        <div className="w-full flex flex-col items-center py-3 border-t border-slate-100">
          {footer.map(renderItem)}
        </div>
      )}
    </aside>
  )
}
