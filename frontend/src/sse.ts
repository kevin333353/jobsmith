// 讀取 fetch 的 SSE 串流（POST 無法用 EventSource，改用 ReadableStream）。
// 泛型 T 由呼叫端標註的 callback 參數型別推導（如 readSSE(resp, (ev: JobsAutoEvent) => ...)）。
export async function readSSE<T>(resp: Response, onEvent: (ev: T) => void) {
  if (!resp.ok || !resp.body) {
    throw new Error(`伺服器回應異常（HTTP ${resp.status}）`)
  }
  const reader = resp.body.getReader()
  const dec = new TextDecoder()
  let buf = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const line = chunk.split("\n").find((l) => l.startsWith("data:"))
      if (!line) continue
      let data: T
      try {
        data = JSON.parse(line.slice(5).trim()) as T
      } catch {
        continue  // 略過單筆毀損的 SSE，續讀後面，不中斷整段串流
      }
      onEvent(data)
    }
  }
}
