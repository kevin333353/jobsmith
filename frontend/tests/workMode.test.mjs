import test from "node:test"
import assert from "node:assert/strict"

import {
  appendWorkModeFilter,
  jobWorkModeBadge,
  normalizeWorkModeFilters,
} from "../src/lib/workMode.ts"

test("normalizes persisted work mode filters", () => {
  assert.deepEqual(
    normalizeWorkModeFilters(["remote", "garbage", "hybrid", "remote"]),
    ["remote", "hybrid"],
  )
  assert.deepEqual(normalizeWorkModeFilters("remote"), [])
})

test("appends work mode and inference policy only when active", () => {
  const inactive = new FormData()
  appendWorkModeFilter(inactive, [], true)
  assert.equal(inactive.has("work_mode"), false)

  const active = new FormData()
  appendWorkModeFilter(active, ["remote", "hybrid"], false)
  assert.equal(active.get("work_mode"), "remote,hybrid")
  assert.equal(active.get("include_inferred_work_mode"), "false")
})

test("labels source metadata separately from text inference", () => {
  assert.deepEqual(
    jobWorkModeBadge({ work_mode: "remote", work_mode_origin: "source" }),
    { label: "來源標示：完全遠端", tone: "emerald" },
  )
  assert.deepEqual(
    jobWorkModeBadge({ work_mode: "hybrid", work_mode_origin: "inferred" }),
    { label: "JD 文字推測：部分／混合遠端", tone: "amber" },
  )
  assert.equal(
    jobWorkModeBadge({ work_mode: "unknown", work_mode_origin: "unknown" }),
    null,
  )
})
