# Security notes

- Store `GEMINI_API_KEY` only as a GitHub Actions repository secret.
- Store one fine-grained GitHub token in Supabase Edge Function secrets, limited to this repository with only **Actions: read and write**.
- Never expose that token in the dashboard. Members authenticate only with Supabase and do not need GitHub accounts.
- Never paste a token into an issue, commit, workflow input, Actions log, or shared document.
- The repository must be public for free standard runner usage, so treat campaign inputs and result metadata as non-confidential.
- Revoke and rotate the server-side token immediately if it is exposed.
- `requested_by` is display-only. Never use it, a browser-supplied `user_id`, or `raw_user_meta_data` for authorization.
- Keep the GitHub token and callback secret in Edge Function secrets, perform GitHub calls only in Edge Functions, and enforce ownership/admin access with the migrations in `supabase/migrations/`.
- The browser may contain only the Supabase URL and publishable key. Never expose a secret/service-role key through a `VITE_` variable.
- Keep screenshot buckets private. Members receive no general cross-user read/list policy; admins use short-lived signed URLs.

The validation script scans committed text for common GitHub and Google token formats, but it is a last guard—not a substitute for careful secret handling.
