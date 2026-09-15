# Source completeness

Last source review: September 15, 2026.

This repository contains the core ClipFarm application, not a complete export of the latest hosted workspace. Local tests establish behavior covered by those tests; they do not certify the production database, authorization policies, or video-processing services.

## Feature coverage

| Capability | Checked-in status | Remaining work |
|---|---|---|
| Email/password sign-in and signup | Frontend and base schema present | Verify email delivery and account policy in an isolated deployment |
| User-owned campaigns and status rows | Frontend, schema, dispatch, and callbacks present | Test two members against a configured private worker |
| Admin campaign totals and commission accounting | Frontend and database functions present | Verify role isolation and concurrent accounting updates against PostgreSQL |
| Screenshot uploads, review, and member lockout | Frontend and base database policies present | Test upload, deadline, review, and payment end to end |
| Invite-only registration | Not integrated | Backend source recovered separately; matching invitation migrations and frontend still needed |
| Admin account removal | Not integrated | Backend source recovered separately; UI, deletion semantics, and authorization tests still needed |
| Complete admin exemption from the seven-day rule | Not integrated | Synchronize dispatch, access calculation, reminders, and frontend behavior together |
| Earnings-review status in Team overview | Not integrated | Distinguish campaign counts from screenshot-review counts and refresh consistently after mutations |

The Team overview's existing pending/completed columns describe **campaign processing**. Accepting an earnings screenshot does not change a campaign's processing state. The pending-review badge is a separate count and currently queries only the latest 50 submissions; it is not a reliable all-time total for larger teams. Member history also uses bounded queries (30 runs and 8 submissions).

## Recovery boundary

Deployed Edge Function source was recovered for registration, account removal, campaign dispatch, callbacks, and downloads. Recovered files are being held outside the deployable source tree until their dependencies are verified. Copying individual functions into this repository would not reproduce the latest application and could produce a broken setup.

At the initial recovery check, the database project was inactive. It was resumed on September 15; database connectivity and the Auth health endpoint were verified afterward. The available hosting account still did not provide access to the dashboard's owning project, so the latest frontend has not been recovered or redeployed. No production account data, invitation codes, passwords, or service credentials belong in this repository or its test fixtures.

The checked-in frontend now defers database work until after Auth callbacks release their lock, displays actionable network-error messages, and offers a retry when workspace initialization fails. This improves recovery behavior; it cannot itself resume a paused backend. Full real-account sign-in and deployment parity remain separate verification steps.

## Completion criteria

- Recover and compare the latest frontend source, database migrations, and Edge Functions.
- Preserve repository fixes that are newer than the recovered deployment.
- Apply the complete migration sequence to an isolated database.
- Verify two fictional members see only their own campaigns, earnings, and files.
- Verify a member cannot invoke admin operations or gain privileges through editable metadata.
- Verify admins remain exempt after the deadline and account removal rejects self-removal and protected admins.
- Verify review acceptance updates the queue, history, per-user review counts, and commission balance without changing campaign counts or losing in-progress form edits.
- Scan tracked files and history for secrets; review fixtures, images, and commit metadata for personal information.
- Run the automated suite, build the dashboard, and verify a complete private-worker run before asserting end-to-end parity.

Live-team accounts are not portfolio demo accounts. Use an isolated instance with fictional data for screenshots or employer demonstrations.
