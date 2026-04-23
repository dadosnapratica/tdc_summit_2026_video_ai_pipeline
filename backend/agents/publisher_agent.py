"""publisher_agent — upload YouTube Data API v3 (privacyStatus via env, default private)."""
from __future__ import annotations

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from workshop.backend.core.state import VideoState

logger = logging.getLogger(__name__)


def _build_credentials() -> Credentials:
    client_id = (os.getenv("YOUTUBE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("YOUTUBE_CLIENT_SECRET") or "").strip()
    refresh = (os.getenv("YOUTUBE_REFRESH_TOKEN") or "").strip()
    if not (client_id and client_secret and refresh):
        raise RuntimeError("OAuth YouTube incompleto (CLIENT_ID/SECRET/REFRESH_TOKEN)")

    return Credentials(
        token=None,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )


def publisher_agent(state: VideoState) -> VideoState:
    if os.getenv("SKIP_YOUTUBE_UPLOAD", "").strip().lower() in ("1", "true", "yes"):
        logger.info("[publisher_agent] SKIP_YOUTUBE_UPLOAD ativo — sem upload")
        return {**state, "publish_status": None}

    video_path = str(state.get("video_file") or "")
    meta = state.get("metadata") or {}
    title = str(meta.get("title") or "Sem título")[:100]
    description = str(meta.get("description") or "")
    tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
    tags = [str(t) for t in tags][:30]

    privacy = (os.getenv("PUBLISH_PRIVACY_STATUS") or "private").strip()
    category_id = (os.getenv("YOUTUBE_CATEGORY_ID") or "28").strip()

    if not video_path or not os.path.isfile(video_path):
        logger.warning("[publisher_agent] sem video_file — skip upload")
        return {**state, "publish_status": None}

    try:
        creds = _build_credentials()
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        body = {
            "snippet": {"title": title, "description": description, "tags": tags, "categoryId": category_id},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                logger.info("[publisher_agent] upload %d%%", int(status.progress() * 100))
        vid = str((resp or {}).get("id", "")).strip()
        if not vid:
            raise RuntimeError(f"Resposta sem id: {resp}")
        return {**state, "publish_status": f"uploaded:{vid}"}
    except Exception as e:
        logger.error("[publisher_agent] falha no upload: %s", e)
        return {**state, "publish_status": f"error:{e}"}
