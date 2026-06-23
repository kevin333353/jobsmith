export function ScoreRing({ score }: { score: number }) {
  const r = 52, c = 2 * Math.PI * r
  const offset = c * (1 - score / 100)
  const color = score >= 80 ? "#059669" : score >= 60 ? "#d97706" : "#dc2626"
  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#e2e8f0" strokeWidth="12" />
      <circle cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="12"
        strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
        transform="rotate(-90 70 70)" />
      <text x="70" y="66" textAnchor="middle" fontSize="32" fontWeight="700" fill="#0f172a">{score}</text>
      <text x="70" y="90" textAnchor="middle" fontSize="13" fill="#64748b">/ 100</text>
    </svg>
  )
}
