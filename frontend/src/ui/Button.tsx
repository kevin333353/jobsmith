import type { ButtonHTMLAttributes, ComponentType, ReactNode } from "react"
import { Loader2 } from "./icons"

type Variant = "primary" | "secondary" | "ghost" | "danger"
type Size = "sm" | "md"

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm focus-visible:ring-brand-300",
  secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 focus-visible:ring-slate-300",
  ghost: "text-brand-700 hover:bg-brand-50 focus-visible:ring-brand-200",
  danger: "bg-rose-600 text-white hover:bg-rose-700 focus-visible:ring-rose-300",
}
const SIZES: Record<Size, string> = { sm: "px-3 py-1.5 text-sm", md: "px-4 py-2 text-sm" }

export function Button(
  { variant = "primary", size = "md", icon: Icon, loading = false, children, className = "", disabled, ...rest }:
  {
    variant?: Variant
    size?: Size
    icon?: ComponentType<{ className?: string }>
    loading?: boolean
    children?: ReactNode
  } & ButtonHTMLAttributes<HTMLButtonElement>,
) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition
        focus:outline-none focus-visible:ring-2 disabled:opacity-50 disabled:pointer-events-none
        ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {loading
        ? <Loader2 className="w-4 h-4 animate-spin" />
        : Icon ? <Icon className="w-4 h-4" /> : null}
      {children}
    </button>
  )
}
