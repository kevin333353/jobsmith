import { useState } from "react"
import type { KeyboardEvent as ReactKeyboardEvent } from "react"
import {
  MAX_TARGET_ROLES,
  normalizeTargetRoles,
} from "../../lib/localDiscovery"
import { Loader2, Target, X } from "../../ui/icons"

interface Props {
  roles: string[]
  suggestions?: string[]
  onChange: (roles: string[]) => void
  disabled?: boolean
  loading?: boolean
  previewError?: string
}

export function TargetRoleEditor({
  roles,
  suggestions = [],
  onChange,
  disabled = false,
  loading = false,
  previewError = "",
}: Props) {
  const [input, setInput] = useState("")

  function addRoles(raw: string) {
    const next = normalizeTargetRoles([...roles, raw])
    if (next.length !== roles.length || next.some((role, index) => role !== roles[index])) {
      onChange(next)
    }
    setInput("")
  }

  function removeRole(role: string) {
    onChange(roles.filter((item) => item !== role))
  }

  function onKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === "," || event.key === "，" || event.key === "、") {
      event.preventDefault()
      addRoles(input)
    } else if (event.key === "Backspace" && !input && roles.length) {
      onChange(roles.slice(0, -1))
    }
  }

  const remainingSuggestions = suggestions.filter((role) => !roles.includes(role))

  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-center justify-between gap-1">
        <label htmlFor="target-role-input" className="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
          <Target className="h-4 w-4 text-brand-500" />
          想找什麼工作？
        </label>
        <span className="text-[11px] text-slate-400">最多 {MAX_TARGET_ROLES} 個，可直接修改</span>
      </div>
      <div className="flex min-h-11 flex-wrap items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-2.5 py-2 focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-100">
        {roles.map((role) => (
          <span
            key={role}
            className="inline-flex items-center gap-1 rounded-lg bg-brand-50 py-1 pl-2.5 pr-1.5 text-sm font-medium text-brand-700"
          >
            {role}
            <button
              type="button"
              onClick={() => removeRole(role)}
              disabled={disabled}
              aria-label={`移除目標職稱 ${role}`}
              className="rounded p-0.5 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 disabled:opacity-50"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {roles.length < MAX_TARGET_ROLES && (
          <input
            id="target-role-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            onBlur={() => addRoles(input)}
            disabled={disabled}
            placeholder={roles.length ? "再加一個職稱…" : "例如：護理師、產品經理"}
            className="min-w-[11rem] flex-1 bg-transparent py-0.5 text-sm outline-none placeholder:text-slate-400 disabled:opacity-50"
          />
        )}
      </div>
      <div className="mt-1.5 min-h-5 text-xs">
        {loading ? (
          <span className="inline-flex items-center gap-1 text-brand-600">
            <Loader2 className="h-3 w-3 animate-spin" />
            正在本機辨識履歷職稱…
          </span>
        ) : previewError ? (
          <span className="text-amber-700">{previewError}，仍可手動輸入後搜尋。</span>
        ) : roles.length ? (
          <span className="text-slate-500">會優先用這些職稱搜尋；不在詞庫內也可以。</span>
        ) : remainingSuggestions.length ? (
          <span className="inline-flex flex-wrap items-center gap-1 text-slate-500">
            履歷原本的方向：
            {remainingSuggestions.map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => addRoles(role)}
                disabled={disabled}
                className="rounded-md bg-slate-100 px-1.5 py-0.5 text-slate-700 hover:bg-slate-200 disabled:opacity-50"
              >
                ＋{role}
              </button>
            ))}
          </span>
        ) : (
          <span className="text-slate-400">可留空讓系統自動判斷；辨識不準時再改即可。</span>
        )}
      </div>
    </div>
  )
}
