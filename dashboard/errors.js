export function errorMessage(error, fallback = "The request could not be completed.", online = globalThis.navigator?.onLine) {
  if (online === false) return "You appear to be offline. Reconnect to the internet and try again.";
  const message = typeof error?.message === "string" ? error.message : "";
  if (/failed to fetch|fetch failed|networkerror|network request failed|load failed|failed to send a request to the edge function/i.test(message)) {
    return "Cannot reach ClipFarm's backend. Check your connection and try again. If this continues, ask the administrator to check that the Supabase project is active.";
  }
  if (["AbortError", "TimeoutError"].includes(error?.name)) {
    return "The request timed out. Check your connection. Before resubmitting a campaign or payment, refresh to see whether it was saved.";
  }
  return message || fallback;
}
