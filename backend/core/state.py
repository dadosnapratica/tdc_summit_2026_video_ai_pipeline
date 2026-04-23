"""Contrato VideoState — alinhado a `.cursorrules`."""
from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class VideoState(TypedDict, total=False):
    channel_niche: str
    job_path: str

    topic: str
    angle: str
    trending_data: Dict[str, object]

    script: str
    scenes: List[str]

    raw_assets: List[Dict[str, object]]
    clips: List[str]

    audio_file: str
    video_file: str

    metadata: Dict[str, object]
    thumbnail: Dict[str, object]
    publish_status: Optional[str]


def initial_video_state(*, channel_niche: str, job_path: str) -> VideoState:
    """Estado inicial mínimo para o primeiro nó do grafo."""
    return {
        "channel_niche": channel_niche,
        "job_path": job_path,
        "topic": "",
        "angle": "",
        "trending_data": {},
        "script": "",
        "scenes": [],
        "raw_assets": [],
        "clips": [],
        "audio_file": "",
        "video_file": "",
        "metadata": {},
        "thumbnail": {},
        "publish_status": None,
    }
