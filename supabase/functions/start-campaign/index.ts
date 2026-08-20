import { createClient } from "npm:@supabase/supabase-js@2.112.3";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { ...corsHeaders, "Content-Type": "application/json" },
});

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

function validUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch (_) {
    return false;
  }
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);

  try {
    const authHeader = request.headers.get("Authorization") ?? "";
    const token = authHeader.replace(/^Bearer\s+/i, "");
    if (!token) return json({ error: "Authentication required" }, 401);

    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const publishableKey = envKey("SUPABASE_PUBLISHABLE_KEYS", "SUPABASE_ANON_KEY");
    const secretKey = envKey("SUPABASE_SECRET_KEYS", "SUPABASE_SERVICE_ROLE_KEY");
    if (!supabaseUrl || !publishableKey || !secretKey) {
      return json({ error: "Backend configuration is incomplete" }, 503);
    }

    const userClient = createClient(supabaseUrl, publishableKey, {
      global: { headers: { Authorization: authHeader } },
      auth: { persistSession: false },
    });
    const { data: authData, error: authError } = await userClient.auth.getUser(token);
    if (authError || !authData.user) return json({ error: "Invalid session" }, 401);

    const admin = createClient(supabaseUrl, secretKey, { auth: { persistSession: false } });
    const { data: profile, error: profileError } = await admin
      .from("profiles")
      .select("display_name, earnings_cycle_started_at")
      .eq("id", authData.user.id)
      .single();
    if (profileError || !profile) return json({ error: "Profile not found" }, 403);
    if (Date.now() >= new Date(profile.earnings_cycle_started_at).getTime() + 7 * 86400000) {
      return json({ error: "An earnings screenshot is required before starting another campaign", locked: true }, 423);
    }

    const input = await request.json();
    const platforms = Array.isArray(input.platforms)
      ? input.platforms.filter((item: unknown) => typeof item === "string" && item.length <= 30)
      : [];
    if (typeof input.campaign_name !== "string" || !input.campaign_name.trim() || input.campaign_name.length > 160) {
      return json({ error: "Campaign name is required" }, 400);
    }
    if (!platforms.length || !validUrl(input.episode_url)) {
      return json({ error: "Select a platform and enter a valid source URL" }, 400);
    }
    if (typeof input.requirements !== "string" || !input.requirements.trim() || input.requirements.length > 30000) {
      return json({ error: "Campaign requirements are required" }, 400);
    }
    if (typeof input.available_content === "string" && input.available_content.length > 30000) {
      return json({ error: "Available content is too long" }, 400);
    }

    const runId = crypto.randomUUID();
    const campaign = {
      id: runId,
      user_id: authData.user.id,
      actor_name_snapshot: profile.display_name,
      campaign_name: input.campaign_name.trim(),
      reward_rate: input.reward_rate ?? null,
      minimum_payout: input.minimum_payout ?? null,
      maximum_payout: input.maximum_payout ?? null,
      platforms,
      episode_url: input.episode_url,
      available_content: typeof input.available_content === "string" ? input.available_content.trim() : "",
      requirements: input.requirements.trim(),
      status: "queued",
      current_stage: "queued",
    };
    const { error: insertError } = await admin.from("campaign_runs").insert(campaign);
    if (insertError) throw insertError;
    await admin.from("run_events").insert({
      run_id: runId,
      stage: "queued",
      state: "running",
      message: "Campaign accepted and queued for processing.",
    });

    const owner = Deno.env.get("GITHUB_OWNER") ?? "";
    const repo = Deno.env.get("GITHUB_REPO") ?? "";
    const ref = Deno.env.get("GITHUB_REF") ?? "main";
    const githubToken = Deno.env.get("GITHUB_TOKEN") ?? "";
    if (!owner || !repo || !githubToken) {
      const message = "The processing worker has not been connected by the administrator yet.";
      await admin.from("campaign_runs").update({
        status: "failed", current_stage: "failed", error_stage: "dispatch",
        error_message: message, completed_at: new Date().toISOString(),
      }).eq("id", runId);
      await admin.from("run_events").insert({
        run_id: runId, stage: "failed", state: "failed", message,
      });
      return json({ run_id: runId, status: "failed", warning: message }, 202);
    }

    const payload = {
      schema_version: 1,
      run_id: runId,
      campaign_name: campaign.campaign_name,
      reward_rate: campaign.reward_rate,
      minimum_payout: campaign.minimum_payout,
      maximum_payout: campaign.maximum_payout,
      platforms: campaign.platforms,
      episode_url: campaign.episode_url,
      available_content: campaign.available_content,
      requirements: campaign.requirements,
      requested_by: profile.display_name,
    };
    const githubResponse = await fetch(
      `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/workflows/process_campaign.yml/dispatches`,
      {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${githubToken}`,
          "Content-Type": "application/json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "ClipFarm-Backend/2.0",
        },
        body: JSON.stringify({ ref, inputs: { campaign_json: JSON.stringify(payload) } }),
      },
    );
    if (!githubResponse.ok) {
      const message = `Processing dispatch failed (${githubResponse.status}).`;
      await admin.from("campaign_runs").update({
        status: "failed", current_stage: "failed", error_stage: "dispatch",
        error_message: message, completed_at: new Date().toISOString(),
      }).eq("id", runId);
      await admin.from("run_events").insert({ run_id: runId, stage: "failed", state: "failed", message });
      return json({ run_id: runId, status: "failed", error: message }, 502);
    }

    return json({ run_id: runId, status: "queued" }, 202);
  } catch (error) {
    console.error(error);
    return json({ error: error instanceof Error ? error.message : "Unexpected backend error" }, 500);
  }
});
