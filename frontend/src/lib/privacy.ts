const PERSONAL_CACHE_KEYS = [
  "copilot.jobsearch.v1",
  "copilot.currentRun.v1",
  "copilot.candidateProfiles.v1",
  "copilot.firstRunGuide.dismissed",
]

export function clearLocalPersonalData(storage: Storage = localStorage) {
  for (const key of PERSONAL_CACHE_KEYS) storage.removeItem(key)
}
