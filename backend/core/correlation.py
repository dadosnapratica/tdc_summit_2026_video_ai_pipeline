from __future__ import annotations

import contextvars

# Correlation id propagado por request (UI → BFF → camadas internas).
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    return (correlation_id_var.get() or "").strip()


def set_correlation_id(cid: str) -> None:
    correlation_id_var.set((cid or "").strip())

