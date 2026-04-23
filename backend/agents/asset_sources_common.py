from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


def safe_get(d: Dict[str, Any], path: List[str], default: Any = "") -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


@dataclass(frozen=True)
class SearchConfig:
    per_source: int = 5
    timeout_s: int = 25

