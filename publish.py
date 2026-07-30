"""
Publishing via official free APIs only.

YouTube Shorts: YouTube Data API v3 (OAuth), free.
Instagram Reels: Graph API via a tester-account access token (Development
  Mode, no App Review needed at small scale), free.
TikTok: intentionally NOT implemented here until your Content Posting API
  audit clears -- clips instead stay local for manual upload. Don't build
  around unofficial/browser-automation posting; see project notes.

Each function takes a rendered clip path + metadata and returns the
published post URL (or None + a note if not auto-postable yet).
"""

import os

import requests


def publish_youtube_short(clip_path: str, title: str, description: str) -> str:
    """Uploads via YouTube Data API v3. Assumes an OAuth token has already
    been obtained and stored (see README for the one-time auth flow) and
    is available via the YOUTUBE_ACCESS_TOKEN env var / refreshed token."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=os.environ["YOUTUBE_ACCESS_TOKEN"],
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(clip_path, chunksize=-1, resumable=True),
    )
    response = request.execute()
    return f"https://youtube.com/shorts/{response['id']}"


def publish_instagram_reel(clip_public_url: str, caption: str) -> str:
    """Publishes via Instagram Graph API. Requires the clip to be reachable
    at a public URL (e.g. hosted alongside the dashboard), plus an
    IG_USER_ID and IG_ACCESS_TOKEN from a tester account (see README)."""
    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["IG_ACCESS_TOKEN"]

    container = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": clip_public_url,
            "caption": caption,
            "access_token": access_token,
        },
    ).json()

    container_id = container["id"]

    publish = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token},
    ).json()

    return f"https://instagram.com/reel/{publish.get('id', '')}"
