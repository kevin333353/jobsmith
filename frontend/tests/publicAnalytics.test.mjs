import assert from "node:assert/strict"
import test from "node:test"

import {
  publicAnalyticsAttribution,
  publicAnalyticsHeaders,
} from "../src/lib/publicAnalytics.ts"

test("explicit Threads campaign is reduced to bounded attribution fields", () => {
  assert.deepEqual(
    publicAnalyticsAttribution(
      "?utm_source=threads&utm_campaign=Threads_202607",
      "",
      "jobsmith-web.onrender.com",
    ),
    { source: "threads", campaign: "threads_202607" },
  )
})

test("known referrers are categorized without forwarding their URL", () => {
  const headers = publicAnalyticsHeaders(
    "",
    "https://github.com/kevin333353/jobsmith/issues?private=value",
    "jobsmith-web.onrender.com",
  )

  assert.deepEqual(headers, {
    "X-Jobsmith-Analytics-Source": "github",
    "X-Jobsmith-Analytics-Campaign": "none",
  })
  assert.equal(JSON.stringify(headers).includes("private=value"), false)
})

test("arbitrary UTM values and personal-looking campaigns are not forwarded", () => {
  assert.deepEqual(
    publicAnalyticsAttribution(
      "?utm_source=newsletter&utm_campaign=person%40example.com",
      "https://unknown.example/article?id=123",
      "jobsmith-web.onrender.com",
    ),
    { source: "referral", campaign: "none" },
  )
})

test("same-origin and missing referrers are direct traffic", () => {
  assert.equal(
    publicAnalyticsAttribution(
      "",
      "https://jobsmith-web.onrender.com/results",
      "jobsmith-web.onrender.com",
    ).source,
    "direct",
  )
  assert.equal(publicAnalyticsAttribution("", "", "jobsmith-web.onrender.com").source, "direct")
})
