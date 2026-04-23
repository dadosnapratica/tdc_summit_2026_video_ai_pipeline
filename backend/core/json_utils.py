"""Parsing defensivo de JSON devolvido por LLMs."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def clean_json_fences(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s.removesuffix("```").strip()
    return s


def _extract_first_jsonish(clean: str) -> str:
    """
    Best-effort: extrai o primeiro objeto/array JSON quando o LLM devolve texto extra.
    Não garante validade; apenas tenta reduzir ruído.
    """
    s = (clean or "").strip()
    if not s:
        return ""
    # tenta achar um objeto {...} ou array [...]
    m_obj = re.search(r"\{[\s\S]*\}", s)
    m_arr = re.search(r"\[[\s\S]*\]", s)
    # escolhe o primeiro que aparecer no texto
    candidates = []
    if m_obj:
        candidates.append((m_obj.start(), m_obj.group(0)))
    if m_arr:
        candidates.append((m_arr.start(), m_arr.group(0)))
    if not candidates:
        return s
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1].strip()


def parse_llm_json(raw: str) -> Any:
    clean = clean_json_fences(raw)
    try:
        return json.loads(clean)
    except Exception:
        extracted = _extract_first_jsonish(clean)
        if extracted and extracted != clean:
            return json.loads(extracted)
        raise


def parse_llm_json_safe(raw: str, *, default: Any) -> Any:
    try:
        return parse_llm_json(raw)
    except Exception as e:
        clean = clean_json_fences(raw)
        snippet = (clean[:200] if clean else "").replace("\n", " ").strip()
        logger.warning("[json_utils] parse falhou: %s (len=%s, snippet=%r)", e, len(clean or ""), snippet)
        return default
