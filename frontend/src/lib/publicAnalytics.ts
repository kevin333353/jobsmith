export type PublicAnalyticsAttribution = {
  source: "direct" | "threads" | "github" | "google" | "facebook" | "instagram" | "x" | "referral" | "other"
  campaign: string
}

const TRACKING_SLUG = /^[a-z0-9][a-z0-9._-]{0,39}$/i

function trackingSlug(value: string | null): string {
  const normalized = (value || "").trim().toLowerCase()
  return TRACKING_SLUG.test(normalized) ? normalized : ""
}

function sourceFromReferrer(referrer: string, currentHostname: string): PublicAnalyticsAttribution["source"] {
  if (!referrer) return "direct"
  try {
    const hostname = new URL(referrer).hostname.toLowerCase().replace(/\.$/, "")
    const current = currentHostname.toLowerCase().replace(/\.$/, "")
    if (!hostname || hostname === current) return "direct"
    if (hostname === "threads.net" || hostname.endsWith(".threads.net") || hostname === "threads.com") {
      return "threads"
    }
    if (hostname === "github.com" || hostname.endsWith(".github.com")) return "github"
    if (hostname === "google.com" || hostname.startsWith("google.") || hostname.includes(".google.")) {
      return "google"
    }
    if (hostname === "facebook.com" || hostname.endsWith(".facebook.com")) return "facebook"
    if (hostname === "instagram.com" || hostname.endsWith(".instagram.com")) return "instagram"
    if (hostname === "x.com" || hostname.endsWith(".x.com")
      || hostname === "twitter.com" || hostname.endsWith(".twitter.com")
      || hostname === "t.co") return "x"
    return "referral"
  } catch {
    return "other"
  }
}

export function publicAnalyticsAttribution(
  search: string,
  referrer: string,
  currentHostname: string,
): PublicAnalyticsAttribution {
  const params = new URLSearchParams(search)
  const requestedSource = trackingSlug(params.get("utm_source"))
  const source = (
    requestedSource === "threads"
    || requestedSource === "github"
    || requestedSource === "google"
    || requestedSource === "facebook"
    || requestedSource === "instagram"
    || requestedSource === "x"
  )
    ? requestedSource
    : sourceFromReferrer(referrer, currentHostname)
  return {
    source,
    campaign: trackingSlug(params.get("utm_campaign")) || "none",
  }
}

export function publicAnalyticsHeaders(
  search: string,
  referrer: string,
  currentHostname: string,
): Record<string, string> {
  const attribution = publicAnalyticsAttribution(search, referrer, currentHostname)
  return {
    "X-Jobsmith-Analytics-Source": attribution.source,
    "X-Jobsmith-Analytics-Campaign": attribution.campaign,
  }
}
