# Security notes

- Store `GEMINI_API_KEY` only as a GitHub Actions repository secret.
- Store one fine-grained GitHub token in Supabase Edge Function secrets, limited to the private processing repository with only **Actions: read and write**.
- Never expose that token in the dashboard. Members authenticate only with Supabase and do not need GitHub accounts.
- Never paste a token into an issue, commit, workflow input, Actions log, or shared document.
- This repository may be public for portfolio review. Real campaign processing must run in a private repository: logs, summaries, workflow inputs, and artifacts can contain personal or commercial information. The processing job checks repository visibility before it starts.
- Revoke and rotate the server-side token immediately if it is exposed.
- `requested_by` is display-only. Never use it, a browser-supplied `user_id`, or `raw_user_meta_data` for authorization.
- Keep the GitHub token and callback secret in Edge Function secrets, perform GitHub calls only in Edge Functions, and enforce ownership/admin access with the migrations in `supabase/migrations/`.
- The browser may contain only the Supabase URL and publishable key. Never expose a secret/service-role key through a `VITE_` variable.
- Keep screenshot buckets private. Members receive no general cross-user read/list policy; admins use short-lived signed URLs.

## Before publishing

Run the structure check and scan both files and Git history with Gitleaks:

```bash
python3 scripts/validate_structure.py
gitleaks dir . --redact
gitleaks git . --redact
```

The validation script catches common token patterns. Gitleaks adds broader detection; neither can prove that all sensitive data is absent. Review exports, screenshots, URLs with query tokens, commit author emails, and past Actions logs separately. An ignored file is not removed from Git history if it was previously committed.

Use a GitHub no-reply commit email when keeping a personal email private. Keep real users, passwords, invitation codes, browser session files, and provider credentials out of examples and tests. Use placeholder-only `.env.example` files.

## Reporting a vulnerability

Use the repository's **Security → Report a vulnerability** option if enabled. Do not put credentials, private screenshots, or reproduction data containing customer information in a public issue. If private reporting is unavailable, request a private contact channel without disclosing exploit details.

If a real credential is exposed, revoke and replace it at the provider first. Removing the file or rewriting Git history does not invalidate a copied credential. Review provider activity and affected workflow logs/artifacts. Coordinate history rewrites with collaborators before changing existing commit IDs.
