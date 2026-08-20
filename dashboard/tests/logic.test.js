import test from "node:test";
import assert from "node:assert/strict";
import { cycleLabel, extensionForMime, formatMoney, initials, summarizeRuns, validateScreenshot } from "../logic.js";

test("summarizeRuns keeps user status counts separate", () => {
  assert.deepEqual(summarizeRuns([
    { status: "queued" }, { status: "processing" }, { status: "ready" }, { status: "failed" },
  ]), { total: 4, pending: 2, ready: 1, failed: 1 });
});

test("cycleLabel reports lockout and remaining days", () => {
  const now = new Date("2026-08-20T00:00:00Z");
  assert.equal(cycleLabel("2026-08-19T00:00:00Z", now), "Screenshot required");
  assert.equal(cycleLabel("2026-08-23T00:00:00Z", now), "3 days until screenshot is due");
});

test("screenshot validation enforces type and size", () => {
  assert.equal(extensionForMime("image/webp"), "webp");
  assert.match(validateScreenshot({ type: "application/pdf", size: 100 }), /JPEG/);
  assert.match(validateScreenshot({ type: "image/png", size: 11 * 1024 * 1024 }), /10 MB/);
  assert.equal(validateScreenshot({ type: "image/png", size: 100 }), "");
});

test("display helpers are stable", () => {
  assert.equal(initials("Joe Creator"), "JC");
  assert.equal(formatMoney(12.5), "$12.50");
});
