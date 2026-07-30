import test from "node:test"
import assert from "node:assert/strict"

import {
  DEFAULT_JOB_SEARCH_MODE,
  normalizeTargetRoles,
  normalizeJobSearchMode,
  profileRecognition,
  profileTargetRoles,
} from "../src/lib/localDiscovery.ts"

test("no-AI discovery is the user-facing default", () => {
  assert.equal(DEFAULT_JOB_SEARCH_MODE, "local")
  assert.equal(normalizeJobSearchMode(undefined), "local")
  assert.equal(normalizeJobSearchMode("unexpected"), "local")
  assert.equal(normalizeJobSearchMode("ai"), "ai")
})

test("profile recognition only exposes compact display fields", () => {
  const summary = profileRecognition({
    name: "王小明",
    summary: "產品經理",
    preferred_roles: ["產品經理"],
    skills: ["roadmap", "user research"],
    years_experience: "4",
    raw_text: "不應出現在摘要",
  })

  assert.deepEqual(summary, {
    name: "王小明",
    summary: "產品經理",
    roles: ["產品經理"],
    skills: ["roadmap", "user research"],
    yearsExperience: 4,
  })
})

test("target roles accept unknown occupations, deduplicate, and cap search fan-out", () => {
  assert.deepEqual(
    normalizeTargetRoles(["護理師，寵物美容師", "護理師", "咖啡師", "第四個職稱"]),
    ["護理師", "寵物美容師", "咖啡師"],
  )
})

test("generic fallback labels are not presented as resume role suggestions", () => {
  assert.deepEqual(profileTargetRoles({ preferred_roles: ["一般職缺", "門市人員"] }), ["門市人員"])
})
