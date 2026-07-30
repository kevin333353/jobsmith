export function shouldReuseResumePreview(
  publicWeb: boolean,
  hasFile: boolean,
  hasPreviewProfile: boolean,
  previewBusy: boolean,
): boolean {
  return publicWeb && hasFile && hasPreviewProfile && !previewBusy
}
