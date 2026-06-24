import type { ReactNode } from "react"

type Tone = "brand" | "emerald" | "amber" | "rose" | "slate"

const TONES: Record<Tone, string> = {
  brand: "bg-brand-100 text-brand-700",
  emerald: "bg-emerald-100 text-emerald-700",
  amber: "bg-amber-100 text-amber-700",
  rose: "bg-rose-100 text-rose-700",
  slate: "bg-slate-100 text-slate-600",
}

export function Badge(
  { tone = "slate", children, className = "" }:
  { tone?: Tone; children: ReactNode; className?: string },
) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${TONES[tone]} ${className}`}>
      {children}
    </span>
  )
}
