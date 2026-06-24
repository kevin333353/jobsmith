import type { ComponentType, ReactNode } from "react"

// 空狀態 / 引導：圖示 + 標題 + 說明 + 選用 CTA。
export function EmptyState(
  { icon: Icon, title, desc, action }:
  { icon: ComponentType<{ className?: string }>; title: string; desc?: ReactNode; action?: ReactNode },
) {
  return (
    <div className="text-center py-12 px-6">
      <div className="mx-auto w-14 h-14 rounded-2xl bg-brand-50 text-brand-500 flex items-center justify-center mb-4">
        <Icon className="w-7 h-7" />
      </div>
      <p className="font-medium text-slate-700">{title}</p>
      {desc && <div className="text-sm text-slate-500 mt-1 max-w-md mx-auto">{desc}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}
