import test from "node:test"
import assert from "node:assert/strict"

import { jobExperienceLabel } from "../src/components/jobs/experience.ts"

test("uses the source experience text when available", () => {
  assert.equal(jobExperienceLabel({ experience_text: "3 年以上", min_years: 3 }), "年資 3 年以上")
})

test("formats inferred minimum years", () => {
  assert.equal(jobExperienceLabel({ min_years: 2 }), "年資 2 年以上")
})

test("formats entry-level jobs", () => {
  assert.equal(jobExperienceLabel({ min_years: 0 }), "不限年資")
  assert.equal(jobExperienceLabel({ experience_text: "無經驗", min_years: 0 }), "無經驗")
})

test("returns an empty label when experience is unknown", () => {
  assert.equal(jobExperienceLabel({}), "")
})
