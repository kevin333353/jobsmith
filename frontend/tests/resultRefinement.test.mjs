import test from "node:test"
import assert from "node:assert/strict"

import {
  createEmptyResultRefinement,
  filterJobMatches,
  normalizeResultRefinement,
  resultRefinementActive,
} from "../src/components/jobs/resultRefinement.ts"

function match(overrides = {}) {
  return {
    fit_score: 75,
    matched: [],
    gaps: [],
    reason: "",
    job: {
      source: "104",
      title: "AI Engineer",
      company: "Future Lab",
      location: "台北市",
      salary: "月薪 NT$70,000–100,000",
      url: "https://example.com/job",
      snippet: "Build Python services",
      requirements: ["Python"],
      min_years: 2,
      work_mode: "remote",
      work_mode_origin: "source",
      ...overrides,
    },
  }
}

test("empty refinement keeps the complete ranked pool", () => {
  const matches = [match(), match({ company: "Second Co" })]
  const state = createEmptyResultRefinement()

  assert.deepEqual(filterJobMatches(matches, state), matches)
  assert.equal(resultRefinementActive(state), false)
})

test("combines text, location, source, fit, and experience refinements", () => {
  const keep = match()
  const matches = [
    keep,
    { ...match({ company: "Other", location: "高雄市" }), fit_score: 90 },
    match({ source: "cake", title: "Frontend Engineer" }),
    match({ min_years: 5 }),
  ]
  const state = {
    ...createEmptyResultRefinement(),
    query: "python",
    location: "台北",
    sources: ["104"],
    minFit: 60,
    maxExperienceYears: "3",
  }

  assert.deepEqual(filterJobMatches(matches, state), [keep])
})

test("filters work mode and evidence origin without treating missing metadata as confirmed", () => {
  const confirmedRemote = match()
  const inferredHybrid = match({
    title: "Hybrid role",
    work_mode: "hybrid",
    work_mode_origin: "inferred",
  })
  const unknown = match({
    title: "Unmarked role",
    work_mode: undefined,
    work_mode_origin: undefined,
  })

  assert.deepEqual(filterJobMatches(
    [confirmedRemote, inferredHybrid, unknown],
    { ...createEmptyResultRefinement(), workModes: ["hybrid"], workModeOrigins: ["inferred"] },
  ), [inferredHybrid])
  assert.deepEqual(filterJobMatches(
    [confirmedRemote, inferredHybrid, unknown],
    { ...createEmptyResultRefinement(), workModes: ["unknown"], workModeOrigins: ["unknown"] },
  ), [unknown])
})

test("applies salary refinement locally while retaining unknown experience values", () => {
  const known = match({ min_years: 2 })
  const unknownExperience = match({ title: "No years listed", min_years: null })
  const tooSenior = match({ title: "Senior", min_years: 5 })
  const unknownSalary = match({ title: "Negotiable", min_years: 1, salary: "面議" })
  const state = {
    ...createEmptyResultRefinement(),
    maxExperienceYears: "3",
    minSalary: "60000",
    includeUnknownSalary: false,
  }

  assert.deepEqual(
    filterJobMatches([known, unknownExperience, tooSenior, unknownSalary], state),
    [known, unknownExperience],
  )
})

test("normalizes persisted refinement state and drops unsupported values", () => {
  assert.deepEqual(normalizeResultRefinement({
    query: "AI",
    location: "台北",
    sources: ["104", "", "104", 7],
    workModes: ["remote", "invalid", "hybrid"],
    workModeOrigins: ["source", "bad"],
    minFit: 80,
    maxExperienceYears: "3",
    salaryUnit: "annual",
    minSalary: "1200000",
    maxSalary: "1800000",
    includeUnknownSalary: false,
  }), {
    query: "AI",
    location: "台北",
    sources: ["104"],
    workModes: ["remote", "hybrid"],
    workModeOrigins: ["source"],
    minFit: 80,
    maxExperienceYears: "3",
    salaryUnit: "annual",
    minSalary: "1200000",
    maxSalary: "1800000",
    includeUnknownSalary: false,
  })
})
