import type { JobPosting } from "../types"

// 由職缺欄位組出基本 JD（抓不到完整 JD 時的後備）。
export function buildJd(j: JobPosting): string {
  return [
    j.title,
    `公司：${j.company}`,
    j.location ? `地點：${j.location}` : "",
    j.salary ? `薪資：${j.salary}` : "",
    "",
    j.snippet || "",
    j.requirements.length ? `\n需求：${j.requirements.join("、")}` : "",
  ].filter(Boolean).join("\n")
}

// 產生投遞包前抓「完整 JD」（104 走官方 content API）；抓不到就退回搜尋摘要。
export async function resolveJd(j: JobPosting): Promise<string> {
  let jd = buildJd(j)
  if (!j.url) return jd
  try {
    const r = await fetch("/api/jd/fetch", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: j.url }),
    })
    if (r.ok) {
      const d = await r.json()
      if (d.text && d.text.length > (j.snippet?.length || 0)) {
        const head = [
          d.title || j.title,
          `公司：${d.company || j.company}`,
          j.location ? `地點：${j.location}` : "",
          j.salary ? `薪資：${j.salary}` : "",
        ].filter(Boolean).join("\n")
        jd = `${head}\n\n${d.text}`
      }
    }
  } catch { /* 抓不到就用搜尋摘要 */ }
  return jd
}
