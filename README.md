# ClipFarm Pipeline

Turns a pasted campaign brief + episode link into rendered, captioned,
vertical clips scored for virality — automatically. This is the "engine
room" that the dashboard (built separately, next step) triggers.

## What this does, end to end

1. Downloads the episode (`yt-dlp`)
2. Transcribes it locally (`faster-whisper`, free, no account)
3. Sends the transcript + your campaign brief to Gemini (free tier),
   which returns 5-15 scored clip candidates structured around the
   Hook / Context / Payoff / Loop framework
4. Renders each one: 9:16 crop, burned-in bold captions, 20-35s length
5. (Optional, once configured) auto-publishes to YouTube Shorts and
   Instagram Reels via their official free APIs
6. Everything lands as downloadable GitHub Actions artifacts either way

## One-time setup

### 1. Make this repo public on GitHub
Public repos get **unlimited free GitHub Actions minutes**. Private repos
are capped at 2,000 min/month, which this pipeline will burn through fast
at real volume. Nothing sensitive lives in the code — all keys go in
Secrets below, which stay encrypted even in a public repo.

### 2. Add these as GitHub Secrets
(Repo → Settings → Secrets and variables → Actions → New repository secret)

| Secret name | Where to get it |
|---|---|
| `GEMINI_API_KEY` | ai.google.dev → Get API key (free) |
| `YOUTUBE_ACCESS_TOKEN` / `YOUTUBE_REFRESH_TOKEN` / `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | Google Cloud Console → enable YouTube Data API v3 → OAuth credentials (one-time consent flow, I'll walk you through this) |
| `IG_USER_ID` / `IG_ACCESS_TOKEN` | Meta Developer app → Instagram Graph API → add your account as a Tester (see earlier setup steps) |

Skip the YouTube/IG secrets for now if you just want clips downloadable —
the pipeline still runs and produces clips, it just won't auto-post.

### 3. Trigger a run
This repo listens for a `repository_dispatch` event. The dashboard (next
build step) does this automatically, but you can test it manually right
now with:

```bash
curl -X POST \
  -H "Authorization: token YOUR_GITHUB_PERSONAL_ACCESS_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches \
  -d '{
    "event_type": "process_campaign",
    "client_payload": {
      "campaign_brief": "Paste the Whop campaign rules here",
      "episode_url": "https://youtube.com/watch?v=...",
      "platforms": "youtube,instagram"
    }
  }'
```

Use a **fine-grained personal access token** scoped only to this repo's
Actions — never a broad token, and never paste it anywhere but GitHub
Secrets or your own local terminal.

### 4. Get your results
Go to the repo's **Actions** tab → the running workflow → download the
`clips-*` and `manifest-*` artifacts once it finishes. `manifest.json`
lists every clip with its virality score, hook strength, loop potential,
and suggested caption/hashtags — sorted best-first.

## What's NOT automated (by design)

- **Browsing/picking Whop campaigns** — no public API exists for this;
  stays a fast manual step.
- **Submitting the finished post URL to Whop for payout** — same reason,
  no submission API. ~30 seconds per approved clip.
- **TikTok posting** — automatable once your Content Posting API audit
  clears; until then, download the clip from the artifact and upload
  manually.

## Next step
The dashboard (Lovable) that replaces the manual `curl` command with a
one-click form, and shows you a review queue of finished clips with
post/download buttons.
