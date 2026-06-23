// 讀取 fetch 的 SSE 串流（POST 無法用 EventSource，改用 ReadableStream）。
export async function readSSE(resp: Response, onEvent: (ev: any) => void) {
  const reader = resp.body!.getReader()
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
      if (line) onEvent(JSON.parse(line.slice(5).trim()))
    }
  }
}
