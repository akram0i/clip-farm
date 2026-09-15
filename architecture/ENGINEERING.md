# Engineering walkthrough

ClipFarm explores a common automation problem: connecting a responsive, authenticated web interface to work that is too slow and resource-intensive for a normal HTTP request.

## Design decisions

| Decision | Reason | Tradeoff |
|---|---|---|
| Store campaign runs in PostgreSQL | Ownership and state survive browser sessions | Requires migrations and access-policy verification |
| Separate dashboard, Edge Functions, and Python worker | Keep credentials server-side and video processing off request handlers | Multiple services must be configured together |
| Run Whisper locally in the worker | Word timestamps support captions derived from the source audio | CPU time and model downloads affect latency |
| Validate model-selected moments deterministically | Check duration, transcript bounds, required text, and hashtags | Semantic brand compliance still needs human judgment |
| Sign status callbacks | Authenticate worker updates without giving the worker broad database access | Both ends must share and protect the signing secret |
| Separate upload from earnings review | A member regains access when they submit; admin review can happen later | A screenshot is evidence for human review, not proof of earnings |
| Use a private processing repository | Keep campaign data out of a public portfolio's workflow output | Private compute quotas must be budgeted |

## Read the implementation

1. `dashboard/app.js` — sign-in, member queries, campaign submission, and admin interactions.
2. `supabase/migrations/` — schema, ownership policies, review functions, and commission accounting.
3. `supabase/functions/start-campaign/index.ts` — authorization, durable run creation, and dispatch.
4. `pipeline/main.py` — individual pipeline stages, status, failure records, and results.
5. `pipeline/constraints.py` and `pipeline/moment_picker.py` — candidate selection and deterministic checks.
6. `pipeline/callback.py` — signed worker status delivery.

## Verification

CI checks repository structure, Python compilation and unit tests, dashboard logic tests, and the production frontend build. Tests exercise campaign validation, duration constraints, captions, callback signatures, data contracts, and supported source-link handling.

```bash
python3 scripts/validate_structure.py
python3 -m unittest discover -s tests -v
cd dashboard
npm ci
npm test
npm run build
```

These checks do not replace a configured integration test. A full run also needs working provider credentials, a private worker repository, an accessible video, and deployed database migrations and Edge Functions. No performance benchmark or production uptime guarantee is implied.

## Known boundaries

- Download availability depends on source permissions, provider restrictions, and network conditions.
- AI selection can reject all candidates; it should report a failure rather than invent compliant footage.
- Posting to social platforms and submitting payout claims remain manual.
- Earnings are reviewed by a human; the application is not a fraud detection or payment processing service.
- The hosted application contains follow-up work not integrated into this source snapshot. The [source completeness checklist](SOURCE_STATUS.md) identifies the missing features and the verification required before claiming deployment parity.

## Portfolio review

Reviewers can inspect the architecture and tests without production access. For a demonstration, deploy an isolated instance with fictional users and synthetic campaign data. Do not distribute credentials for the live team workspace.
