export function summarizeRuns(runs = []) {
  return runs.reduce((summary, run) => {
    summary.total += 1;
    if (["queued", "processing"].includes(run.status)) summary.pending += 1;
    if (run.status === "ready") summary.ready += 1;
    if (run.status === "failed") summary.failed += 1;
    return summary;
  }, { total: 0, pending: 0, ready: 0, failed: 0 });
}

export function formatMoney(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })
    .format(Number(value || 0));
}

export function initials(name = "") {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "CF";
}

export function cycleLabel(deadlineAt, serverTime = new Date()) {
  const remaining = new Date(deadlineAt).getTime() - new Date(serverTime).getTime();
  if (remaining <= 0) return "Screenshot required";
  const hours = Math.ceil(remaining / 3600000);
  if (hours <= 24) return `${hours}h until screenshot is due`;
  return `${Math.ceil(hours / 24)} days until screenshot is due`;
}

export function extensionForMime(type) {
  return { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" }[type] || "";
}

export function validateScreenshot(file) {
  if (!file) return "Choose an earnings screenshot.";
  if (!extensionForMime(file.type)) return "Use a JPEG, PNG, or WebP image.";
  if (file.size < 1 || file.size > 10 * 1024 * 1024) return "The screenshot must be 10 MB or smaller.";
  return "";
}
