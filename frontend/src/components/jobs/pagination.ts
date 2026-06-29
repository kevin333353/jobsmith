export type PaginationItem = number | "ellipsis"

export function getPaginationItems(currentPage: number, totalPages: number): PaginationItem[] {
  const total = Math.max(1, Math.floor(totalPages))
  const current = Math.min(Math.max(1, Math.floor(currentPage)), total)
  const maxFullPages = 7
  if (total <= maxFullPages) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const pages = new Set<number>([1, total])
  if (current <= 3) {
    for (let n = 2; n <= 4; n += 1) pages.add(n)
  } else if (current >= total - 2) {
    for (let n = total - 3; n < total; n += 1) pages.add(n)
  } else {
    for (let n = current - 2; n <= current + 2; n += 1) pages.add(n)
  }

  const sorted = [...pages].filter((n) => n >= 1 && n <= total).sort((a, b) => a - b)
  const items: PaginationItem[] = []
  for (const page of sorted) {
    const prev = items[items.length - 1]
    if (typeof prev === "number" && page - prev > 1) {
      items.push("ellipsis")
    }
    items.push(page)
  }
  return items
}
