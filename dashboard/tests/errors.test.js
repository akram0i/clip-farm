import test from "node:test";
import assert from "node:assert/strict";
import { errorMessage } from "../errors.js";

test("network errors give actionable guidance without asserting a specific cause", () => {
  for (const message of ["Failed to fetch", "TypeError: fetch failed", "NetworkError when attempting to fetch resource.", "Load failed", "Failed to send a request to the Edge Function"]) {
    assert.match(errorMessage({ message }, "fallback", true), /check that the Supabase project is active/);
  }
});

test("offline and timeout failures are distinguished", () => {
  assert.match(errorMessage(new Error("Failed to fetch"), "fallback", false), /offline/);
  assert.match(errorMessage({ name: "TimeoutError" }, "fallback", true), /Before resubmitting/);
});

test("application errors and missing errors retain useful messages", () => {
  assert.equal(errorMessage(new Error("Invalid login credentials"), "fallback", true), "Invalid login credentials");
  assert.equal(errorMessage(null, "Try again", true), "Try again");
});
