from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def get_with_retry(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout_s: int = 25,
    max_attempts: int = 3,
    base_backoff_s: float = 1.0,
    backoff_mult: float = 2.0,
    jitter_s: float = 0.25,
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504),
    provider: str = "",
) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout_s)
            if r.status_code not in retry_on_status:
                return r

            retry_after = r.headers.get("Retry-After")
            delay = 0.0
            if retry_after:
                try:
                    delay = float(retry_after)
                except Exception:
                    delay = 0.0
            if delay <= 0:
                delay = base_backoff_s * (backoff_mult ** (attempt - 1))
            delay += random.uniform(0.0, max(0.0, jitter_s))

            if attempt >= max_attempts:
                return r
            tag = provider or "http"
            logger.warning("[%s] status=%s retrying in %.2fs (attempt %s/%s)", tag, r.status_code, delay, attempt, max_attempts)
            time.sleep(delay)
        except Exception as e:
            last_exc = e
            if attempt >= max_attempts:
                raise
            delay = base_backoff_s * (backoff_mult ** (attempt - 1)) + random.uniform(0.0, max(0.0, jitter_s))
            tag = provider or "http"
            logger.warning("[%s] exception=%s retrying in %.2fs (attempt %s/%s)", tag, type(e).__name__, delay, attempt, max_attempts)
            time.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("get_with_retry: unreachable")

