import test from "node:test"
import assert from "node:assert/strict"

import {
  appendSalaryFilter,
  parseSalaryRange,
  salaryFilterActive,
  salaryMatchesFilter,
} from "../src/components/jobs/salaryFilter.ts"

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

test("normalizes monthly, annual, compact, and open-ended salaries", () => {
  assert.deepEqual(parseSalaryRange("月薪 NT$60,000–90,000"), {
    minMonthly: 60000,
    maxMonthly: 90000,
    negotiable: false,
  })
  assert.deepEqual(parseSalaryRange("年薪 TWD 1,200,000–1,800,000"), {
    minMonthly: 100000,
    maxMonthly: 150000,
    negotiable: false,
  })
  assert.deepEqual(parseSalaryRange("40K-60K"), {
    minMonthly: 40000,
    maxMonthly: 60000,
    negotiable: false,
  })
  assert.deepEqual(parseSalaryRange("年薪 100萬以上"), {
    minMonthly: 83333.33,
    maxMonthly: null,
    negotiable: false,
  })
})

test("matches overlapping salary ranges and handles unknown salary policy", () => {
  const wanted = {
    unit: "monthly",
    min: "60000",
    max: "100000",
    includeUnknown: false,
  }

  assert.equal(salaryMatchesFilter("月薪 NT$60,000–90,000", wanted), true)
  assert.equal(salaryMatchesFilter("月薪 NT$40,000–50,000", wanted), false)
  assert.equal(salaryMatchesFilter("年薪 TWD 1,500,000–2,100,000", wanted), false)
  assert.equal(salaryMatchesFilter("面議", wanted), false)
  assert.equal(salaryMatchesFilter("面議", { ...wanted, includeUnknown: true }), true)
  assert.equal(salaryMatchesFilter(
    "月薪 NT$60,000–90,000",
    { ...wanted, min: "100000", max: "60000" },
  ), true)
})
