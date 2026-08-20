# Supabase backend architecture

ClipFarm is an authenticated multi-user application. Vercel serves the Vite dashboard; Supabase owns authentication, PostgreSQL data, private screenshot storage, Row Level Security (RLS), and Edge Functions. GitHub Actions remains the video-processing worker because Whisper and FFmpeg do not fit normal serverless execution limits.

## Trust boundaries

- The browser receives only a Supabase publishable key. It never receives a Supabase secret key, GitHub token, callback secret, user role, or centrally configured repository setting.
- Supabase Auth establishes identity. Authorization uses `public.profiles.role` and RLS; editable user metadata is never used for permissions.
- Members can query only their own active-cycle rows. When the seven-day deadline passes, RLS blocks their profile, campaigns, outputs, events, earnings records, and commission account.
- Admin operations re-check the signed-in user's database role inside restricted functions. Hiding the Admin navigation is only a usability detail, not the security boundary.
- Earnings images use the private `earnings-screenshots` bucket. Object policies scope member uploads to their UUID folder and allow short-lived signed reads only to the owner while active or an admin.

## Data model

| Object | Purpose |
|---|---|
| `profiles` | Display name, member/admin role, cycle start, last screenshot time |
| `campaign_runs` | One durable row per submitted campaign, with owner, inputs, state, output, and failure details |
| `run_events` | Append-only pipeline stage history |
| `clip_outputs` | Normalized per-clip metadata from the manifest |
| `earnings_submissions` | Private screenshot path, reporting interval, review, confirmed earnings, and commission snapshot |
| `earnings_reminders` | Server-recorded reminder impressions, capped across devices |
| `commission_accounts` | Agreed rate and stored owed/paid totals per user |
| `commission_payments` | Append-only payment ledger |
| `admin_user_stats` | Security-invoker aggregate visible only when `private.is_admin()` succeeds |

The executable source of truth is in `supabase/migrations/`. New projects should apply those migrations in timestamp order.

## Seven-day cycle

The account-creation trigger starts the cycle at signup. `get_access_status()` uses database time, not the browser clock. During the first six 24-hour windows it can record at most two reminders per rolling day with at least eight hours between them.

At `cycle_started_at + 168 hours`, member RLS policies fail closed. The screenshot upload policy and `finalize_earnings_submission()` remain available so the member can recover. Successful finalization locks the profile row, records the just-ended reporting interval, and resets the cycle in one transaction. Admin review is not part of unlocking.

## Campaign dispatch and status

`start-campaign` validates the caller and cycle, derives `user_id` and the display-name snapshot from the session, inserts the campaign row, and then reads GitHub configuration only from Edge Function secrets. A dispatch failure is persisted as a visible failed run rather than losing the user's request.

The pipeline signs each callback over the exact compact JSON body. `run-callback` verifies the HMAC before updating `campaign_runs` and appending `run_events`. Configure these server-side values:

When a run is ready, `download-results` verifies that the caller owns the Supabase run row (or is an admin), uses the central GitHub token to request the matching artifact, and returns only a short-lived download redirect. Members never visit GitHub or supply a token.

- Edge Function: `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_REF`, `GITHUB_TOKEN`, `CLIPFARM_CALLBACK_SECRET`
- GitHub Actions: `GEMINI_API_KEY`, `CLIPFARM_CALLBACK_URL`, `CLIPFARM_CALLBACK_SECRET`

No member needs a GitHub account or token.

## Commission semantics

The admin enters new earnings for the saved reporting interval. The first review snapshots the user's configured rate and calculates `round(confirmed_earnings × rate, 2)`. Corrections preserve that historical rate and apply only the balance delta. Payments cannot exceed outstanding commission and are retained as ledger rows.

This is a trust-and-friction workflow. A screenshot can be edited, so the system intentionally uses human review rather than claiming fraud-proof verification or OCR certainty.
