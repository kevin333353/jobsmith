import test from "node:test"
import assert from "node:assert/strict"

import { getPaginationItems } from "../src/components/jobs/pagination.ts"

test("shows every page when the page count is small", () => {
  assert.deepEqual(getPaginationItems(4, 7), [1, 2, 3, 4, 5, 6, 7])
})

test("keeps pagination compact around the current page", () => {
  assert.deepEqual(
    getPaginationItems(30, 59),
    [1, "ellipsis", 28, 29, 30, 31, 32, "ellipsis", 59],
  )
})

test("keeps the first pages visible near the start", () => {
  assert.deepEqual(getPaginationItems(1, 12), [1, 2, 3, 4, "ellipsis", 12])
})

test("keeps the last pages visible near the end", () => {
  assert.deepEqual(getPaginationItems(12, 12), [1, "ellipsis", 9, 10, 11, 12])
})
