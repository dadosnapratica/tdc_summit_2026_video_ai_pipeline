"""Paths NFS e job_id — sem valores hardcoded de rede."""
from __future__ import annotations

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def make_job_path(niche: str) -> str:
    """
    Gera `{PIPELINE_JOBS_PATH}/{slug}_{YYYYMMDD}_{HHMMSS}` e cria `assets/` e `clips/`.
    Convenção de slug: nicho em minúsculas, espaços -> underscore, máx. 20 chars.
    """
    slug = niche.lower().replace(" ", "_")[:20] or "job"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.getenv("PIPELINE_JOBS_PATH", "").strip()
    if not base:
        try:
            from backend.runtime_paths import monorepo_root

            base = str(monorepo_root() / "workshop" / "nas" / "jobs")
        except Exception as e:
            base = os.path.join(os.getcwd(), "video_pipeline_jobs")
            logger.warning(
                "[make_job_path] PIPELINE_JOBS_PATH não definido; monorepo_root falhou (%s); cwd: %s",
                e,
                base,
            )
        else:
            logger.warning(
                "[make_job_path] PIPELINE_JOBS_PATH não definido; usando workshop/nas/jobs: %s",
                base,
            )
    path = os.path.join(base, f"{slug}_{ts}")
    os.makedirs(os.path.join(path, "assets"), exist_ok=True)
    os.makedirs(os.path.join(path, "clips"), exist_ok=True)
    return path
