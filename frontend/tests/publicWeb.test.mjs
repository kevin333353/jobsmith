import assert from "node:assert/strict"
import test from "node:test"

import { shouldReuseResumePreview } from "../src/lib/publicWeb.ts"

test("public Web reuses a completed file preview instead of uploading the resume twice", () => {
  assert.equal(shouldReuseResumePreview(true, true, true, false), true)
  assert.equal(shouldReuseResumePreview(true, true, true, true), false)
  assert.equal(shouldReuseResumePreview(true, true, false, false), false)
  assert.equal(shouldReuseResumePreview(false, true, true, false), false)
})
