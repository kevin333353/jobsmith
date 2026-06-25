import { Component } from "react"
import type { ErrorInfo, ReactNode } from "react"

// 攔截 render 期間的未預期例外，避免整頁白屏；提供重新整理的退路。
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI 發生未預期錯誤：", error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen grid place-items-center p-6 text-center">
          <div className="max-w-md">
            <h1 className="text-lg font-bold text-slate-900 mb-2">頁面發生未預期的錯誤</h1>
            <p className="text-sm text-slate-600 mb-4">
              可以重新整理再試一次；若持續發生，請確認後端伺服器是否正常運作。
            </p>
            <button
              onClick={() => location.reload()}
              className="px-4 py-2 text-sm rounded-lg font-medium bg-brand-600 text-white hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
            >
              重新整理
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
