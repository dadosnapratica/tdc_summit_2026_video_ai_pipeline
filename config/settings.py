"""Leitura centralizada de variáveis de ambiente (sem valores de rede hardcoded)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from core.tts_provider_config import tts_provider_effective


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    comfyui_base_url: str
    comfyui_model: str
    animatediff_model: str
    img2img_strength: float
    animatediff_frames: int
    animatediff_fps: int
    pipeline_jobs_path: str
    nas_mount_path: str
    youtube_api_key: str
    youtube_region: str
    youtube_category_id: str
    youtube_max_results: int
    publish_privacy_status: str
    tts_provider: str
    pexels_api_key: str
    pixabay_api_key: str
    unsplash_access_key: str


def load_settings() -> Settings:
    return Settings(
        ollama_base_url=(os.getenv("OLLAMA_BASE_URL") or "").strip(),
        ollama_model=(os.getenv("OLLAMA_MODEL") or "llama3").strip(),
        comfyui_base_url=(os.getenv("COMFYUI_BASE_URL") or "").strip(),
        comfyui_model=(os.getenv("COMFYUI_MODEL") or "").strip(),
        animatediff_model=(os.getenv("ANIMATEDIFF_MODEL") or "").strip(),
        img2img_strength=float(os.getenv("IMG2IMG_STRENGTH", "0.45")),
        animatediff_frames=int(os.getenv("ANIMATEDIFF_FRAMES", "16")),
        animatediff_fps=int(os.getenv("ANIMATEDIFF_FPS", "8")),
        pipeline_jobs_path=(os.getenv("PIPELINE_JOBS_PATH") or "").strip(),
        nas_mount_path=(os.getenv("NAS_MOUNT_PATH") or "").strip(),
        youtube_api_key=(os.getenv("YOUTUBE_API_KEY") or "").strip(),
        youtube_region=(os.getenv("YOUTUBE_REGION_CODE") or "BR").strip(),
        youtube_category_id=(os.getenv("YOUTUBE_CATEGORY_ID") or "28").strip(),
        youtube_max_results=int(os.getenv("YOUTUBE_MAX_TRENDING_RESULTS", "10")),
        publish_privacy_status=(os.getenv("PUBLISH_PRIVACY_STATUS") or "private").strip(),
        tts_provider=tts_provider_effective(),
        pexels_api_key=(os.getenv("PEXELS_API_KEY") or "").strip(),
        pixabay_api_key=(os.getenv("PIXABAY_API_KEY") or "").strip(),
        unsplash_access_key=(os.getenv("UNSPLASH_ACCESS_KEY") or "").strip(),
    )
