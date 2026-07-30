import test from "node:test"
import assert from "node:assert/strict"

import { describeSearchScope } from "../src/lib/searchScope.ts"

const DEFAULT_SCOPE = {
  regions: [],
  workModes: [],
  includeInferredWorkMode: false,
  maxExperienceYears: "",
  salaryUnit: "monthly",
  minSalary: "",
  maxSalary: "",
  includeUnknownSalary: true,
  companies: [],
  pages: 2,
}

test("default scope stays calm and requires no choices", () => {
  assert.deepEqual(describeSearchScope(DEFAULT_SCOPE), {
    activeCount: 0,
    items: ["全台", "不限工作型態"],
  })
})

test("scope summary exposes active choices without expanding the form", () => {
  assert.deepEqual(describeSearchScope({
    ...DEFAULT_SCOPE,
    regions: ["台北市", "新北市"],
    workModes: ["remote"],
    includeInferredWorkMode: true,
    minSalary: "50000",
    companies: ["A 公司"],
    pages: 3,
  }), {
    activeCount: 5,
    items: ["2 個地區", "完全遠端（含推測）", "月薪 50000", "1 間指定公司", "每站 3 頁"],
  })
})
