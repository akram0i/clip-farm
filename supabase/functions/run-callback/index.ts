import { createClient } from "npm:@supabase/supabase-js@2.112.3";

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

function hex(bytes: ArrayBuffer): string {
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (request) => {
  if (request.method !== "POST") return Response.json({ error: "Method not allowed" }, { status: 405 });
  try {
    const rawBody = await request.text();
    const supplied = request.headers.get("X-ClipFarm-Signature") ?? "";
    const secret = Deno.env.get("CLIPFARM_CALLBACK_SECRET") ?? "";
    if (!secret || !supplied.startsWith("sha256=")) {
      return Response.json({ error: "Missing callback signature" }, { status: 401 });
    }
    const key = await crypto.subtle.importKey(
      "raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
    );
    const expected = `sha256=${hex(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(rawBody)))}`;
    const suppliedBytes = new TextEncoder().encode(supplied);
    const expectedBytes = new TextEncoder().encode(expected);
    if (suppliedBytes.length !== expectedBytes.length) {
      return Response.json({ error: "Invalid callback signature" }, { status: 401 });
    }
    let mismatch = 0;
    for (let index = 0; index < suppliedBytes.length; index += 1) mismatch |= suppliedBytes[index] ^ expectedBytes[index];
    if (mismatch !== 0) return Response.json({ error: "Invalid callback signature" }, { status: 401 });

    const payload = JSON.parse(rawBody);
    if (typeof payload.run_id !== "string" || typeof payload.stage !== "string"
      || typeof payload.state !== "string" || typeof payload.message !== "string") {
      return Response.json({ error: "Invalid callback payload" }, { status: 400 });
    }
    const stageMap = new Set(["queued", "downloading", "transcribing", "selecting", "rendering", "ready", "failed"]);
    if (!stageMap.has(payload.stage)) return Response.json({ error: "Unknown stage" }, { status: 400 });

    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const secretKey = envKey("SUPABASE_SECRET_KEYS", "SUPABASE_SERVICE_ROLE_KEY");
    const admin = createClient(supabaseUrl, secretKey, { auth: { persistSession: false } });
    const status = payload.stage === "ready" && payload.state === "complete"
      ? "ready" : payload.state === "failed" || payload.stage === "failed" ? "failed" : "processing";
    const changes: Record<string, unknown> = {
      status,
      current_stage: payload.stage,
      error_stage: status === "failed" ? payload.stage : null,
      error_message: status === "failed" ? payload.message : null,
    };
    if (status === "processing") changes.started_at = payload.updated_at ?? new Date().toISOString();
    if (status === "ready" || status === "failed") changes.completed_at = payload.updated_at ?? new Date().toISOString();
    if (payload.github_run_id) changes.github_run_id = Number(payload.github_run_id);
    if (payload.github_run_url) changes.github_run_url = payload.github_run_url;
    if (payload.output_url) changes.output_url = payload.output_url;

    const { data: run, error } = await admin.from("campaign_runs")
      .update(changes).eq("id", payload.run_id).select("id").maybeSingle();
    if (error) throw error;
    if (!run) return Response.json({ error: "Run not found" }, { status: 404 });
    await admin.from("run_events").insert({
      run_id: payload.run_id, stage: payload.stage, state: payload.state,
      message: payload.message, event_at: payload.updated_at ?? new Date().toISOString(),
    });
    return Response.json({ ok: true });
  } catch (error) {
    console.error(error);
    return Response.json({ error: error instanceof Error ? error.message : "Unexpected callback error" }, { status: 500 });
  }
});
