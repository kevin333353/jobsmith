import test from "node:test"
import assert from "node:assert/strict"

import { filterByMinFit } from "../src/components/jobs/fitFilter.ts"

function match(score) {
  return { fit_score: score }
}

test("keeps every match when minimum fit is zero", () => {
  const matches = [match(30), match(60), match(80)]

  assert.deepEqual(filterByMinFit(matches, 0), matches)
})

test("keeps only matches at or above the requested fit band", () => {
  const matches = [match(59), match(60), match(79), match(80)]

  assert.deepEqual(filterByMinFit(matches, 80), [matches[3]])
  assert.deepEqual(filterByMinFit(matches, 60), [matches[1], matches[2], matches[3]])
})
