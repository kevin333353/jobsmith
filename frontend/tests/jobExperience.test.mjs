import test from "node:test"
import assert from "node:assert/strict"

import { EXPERIENCE_FILTER_OPTIONS, jobExperienceLabel } from "../src/components/jobs/experience.ts"

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

test("labels experience filter as maximum acceptable requirement", () => {
  assert.deepEqual(EXPERIENCE_FILTER_OPTIONS, [
    { value: "", label: "不篩年資" },
    { value: "0", label: "只看新鮮人 / 未標示年資" },
    { value: "1", label: "排除要求超過 1 年" },
    { value: "2", label: "排除要求超過 2 年" },
    { value: "3", label: "排除要求超過 3 年" },
    { value: "5", label: "排除要求超過 5 年" },
  ])
})
