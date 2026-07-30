import test from "node:test"
import assert from "node:assert/strict"

import {
  COMPLETE_APPLICATION,
  QUICK_GENERATION,
  estimateGenerationCalls,
  normalizeGenerationOptions,
  searchAnalysisPayload,
} from "../src/lib/packageGeneration.ts"

test("quick mode is three calls for pasted JD and one call for a reused search result", () => {
  assert.equal(estimateGenerationCalls(QUICK_GENERATION), 3)
  assert.equal(estimateGenerationCalls(QUICK_GENERATION, true), 1)
  assert.equal(estimateGenerationCalls(COMPLETE_APPLICATION), 4)
})

test("normalization deduplicates outputs and disables unused company research", () => {
  assert.deepEqual(normalizeGenerationOptions({
    artifactTargets: ["resume", "resume"],
    companyResearch: true,
    qualityReview: true,
  }), {
    artifactTargets: ["resume"],
    companyResearch: false,
    qualityReview: true,
  })
})

test("search analysis is converted into reusable pipeline models", () => {
  const payload = searchAnalysisPayload("完整 JD", {
    fit_score: 88,
    matched: ["Python"],
    gaps: ["Kubernetes"],
    reason: "高度符合",
    job: {
      source: "104",
      title: "後端工程師",
      company: "未來公司",
      location: "台北",
      salary: null,
      url: "https://example.com",
      snippet: "開發 API",
      requirements: ["Python", "FastAPI"],
      min_years: 2,
    },
  })

  assert.equal(payload.parsed_job?.title, "後端工程師")
  assert.deepEqual(payload.parsed_job?.responsibilities, ["完整 JD"])
  assert.equal(payload.match_report?.score, 88)
  assert.equal(payload.match_report?.recommend_proceed, true)
})
