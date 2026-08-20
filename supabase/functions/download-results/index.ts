import { createClient } from "npm:@supabase/supabase-js@2.112.3";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: corsHeaders });

function envKey(collection: string, legacy: string): string {
  const value = Deno.env.get(collection);
  if (value) {
    try {
      const parsed = JSON.parse(value);
      if (parsed.default) return parsed.default;
    } catch (_) {
      // Fall through to the legacy environment variable.
    }
  }
  return Deno.env.get(legacy) ?? "";
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
  try {
    const authHeader = request.headers.get("Authorization") ?? "";
    const token = authHeader.replace(/^Bearer\s+/i, "");
    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const publishableKey = envKey("SUPABASE_PUBLISHABLE_KEYS", "SUPABASE_ANON_KEY");
    if (!token || !supabaseUrl || !publishableKey) return json({ error: "Authentication required" }, 401);
    const client = createClient(supabaseUrl, publishableKey, {
      global: { headers: { Authorization: authHeader } }, auth: { persistSession: false },
    });
    const { data: authData, error: authError } = await client.auth.getUser(token);
    if (authError || !authData.user) return json({ error: "Invalid session" }, 401);
    const { run_id: runId } = await request.json();
    if (typeof runId !== "string") return json({ error: "Run ID is required" }, 400);

    const { data: run, error: runError } = await client.from("campaign_runs")
      .select("id, status, github_run_id").eq("id", runId).maybeSingle();
    if (runError) throw runError;
    if (!run) return json({ error: "Run not found or access denied" }, 404);
    if (run.status !== "ready" || !run.github_run_id) return json({ error: "Results are not ready" }, 409);

    const owner = Deno.env.get("GITHUB_OWNER") ?? "";
    const repo = Deno.env.get("GITHUB_REPO") ?? "";
    const githubToken = Deno.env.get("GITHUB_TOKEN") ?? "";
    if (!owner || !repo || !githubToken) return json({ error: "The result service is not configured" }, 503);
    const githubHeaders = {
      Accept: "application/vnd.github+json", Authorization: `Bearer ${githubToken}`,
      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ClipFarm-Backend/2.0",
    };
    const listResponse = await fetch(
      `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/runs/${run.github_run_id}/artifacts?per_page=20`,
      { headers: githubHeaders },
    );
    if (!listResponse.ok) return json({ error: "Could not locate the result artifact" }, 502);
    const list = await listResponse.json();
    const artifact = list.artifacts?.find((item: Record<string, unknown>) =>
      item.name === `clipfarm-results-${run.github_run_id}` && !item.expired
    );
    if (!artifact) return json({ error: "The result download has expired or is unavailable" }, 404);
    const archiveResponse = await fetch(artifact.archive_download_url, { headers: githubHeaders, redirect: "manual" });
    const downloadUrl = archiveResponse.headers.get("location");
    if (![302, 303].includes(archiveResponse.status) || !downloadUrl) {
      return json({ error: "Could not prepare the result download" }, 502);
    }
    return json({ download_url: downloadUrl, expires_in_seconds: 60 });
  } catch (error) {
    console.error(error);
    return json({ error: error instanceof Error ? error.message : "Unexpected download error" }, 500);
  }
});
