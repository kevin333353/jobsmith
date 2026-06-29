export const FIT_FILTERS = [
  { value: 0, label: "全部" },
  { value: 80, label: "高" },
  { value: 60, label: "中以上" },
] as const

export function filterByMinFit<T extends { fit_score: number }>(matches: T[], minFit: number): T[] {
  return matches.filter((m) => m.fit_score >= minFit)
}
