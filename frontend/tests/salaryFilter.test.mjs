import test from "node:test"
import assert from "node:assert/strict"

import { appendSalaryFilter, salaryFilterActive } from "../src/components/jobs/salaryFilter.ts"

test("salary filter is inactive when no bounds are set and unknown salaries are kept", () => {
  assert.equal(salaryFilterActive({
    unit: "monthly",
    min: "",
    max: "",
    includeUnknown: true,
  }), false)
})

test("appends annual salary filter fields to FormData", () => {
  const form = new FormData()
  appendSalaryFilter(form, {
    unit: "annual",
    min: "1200000",
    max: "1800000",
    includeUnknown: false,
  })

  assert.equal(form.get("salary_unit"), "annual")
  assert.equal(form.get("min_salary"), "1200000")
  assert.equal(form.get("max_salary"), "1800000")
  assert.equal(form.get("include_unknown_salary"), "false")
})

test("does not append inactive salary filters", () => {
  const form = new FormData()
  appendSalaryFilter(form, {
    unit: "monthly",
    min: "",
    max: "",
    includeUnknown: true,
  })

  assert.equal(form.has("salary_unit"), false)
  assert.equal(form.has("include_unknown_salary"), false)
})
