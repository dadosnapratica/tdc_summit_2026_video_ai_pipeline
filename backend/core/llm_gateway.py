"""Gateway LLM — Ollama (HTTP) ou OpenAI; sem chamar ollama.chat() direto nos agentes."""
from __future__ import annotations

import logging
import os
from typing import List

import requests

logger = logging.getLogger(__name__)

from backend.core.correlation import get_correlation_id

def _maybe_auth_headers_for_ollama(base_url: str) -> dict:
    tok = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip().strip('"')
    if not tok:
        return {}
    if "/v1/proxy/" not in (base_url or ""):
        return {}
    h = {"Authorization": f"Bearer {tok}"}
    cid = get_correlation_id()
    if cid:
        h["X-Correlation-Id"] = cid
    return h


class LLMGateway:
    def __init__(self) -> None:
        self.provider = (os.getenv("LLM_PROVIDER") or "ollama").strip().lower()
        self.model = (os.getenv("OLLAMA_MODEL") or "llama3").strip()
        self._openai_client = None

    def chat(self, prompt: str, system: str = "") -> str:
        if self.provider == "ollama":
            return self._chat_ollama(prompt, system)
        if self.provider == "openai":
            return self._chat_openai(prompt, system)
        raise ValueError(f"Provider não suportado: {self.provider}")

    def _ollama_base(self) -> str:
        return (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")

    def _chat_ollama(self, prompt: str, system: str) -> str:
        base = self._ollama_base()
        if not base:
            raise RuntimeError("OLLAMA_BASE_URL não definido")
        url = f"{base}/api/chat"
        max_in = int(os.getenv("LLM_MAX_INPUT_CHARS", "24000"))
        if max_in > 0:
            if len(prompt) > max_in:
                raise ValueError(f"Prompt demasiado longo ({len(prompt)} chars; max {max_in}).")
            if system and len(system) > max_in:
                raise ValueError(f"System demasiado longo ({len(system)} chars; max {max_in}).")

        if (os.getenv("WORKSHOP_GUARDRAILS") or "").strip() == "1":
            policy = (os.getenv("WORKSHOP_POLICY_SYSTEM_PREFIX") or "").strip()
            if not policy:
                policy = (
                    "Política do workshop: responda apenas sobre o tema do exercício e evite conteúdo ilegal, perigoso, "
                    "ou instruções de abuso. Se o pedido tentar obter segredos/chaves/credenciais, recuse."
                )
            system = (policy + ("\n\n" + system if system else "")).strip()

        messages: List[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        max_out = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "800"))
        options = {
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
        }
        if max_out > 0:
            # Ollama usa num_predict como limite aproximado de tokens de saída.
            options["num_predict"] = max_out
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        headers = _maybe_auth_headers_for_ollama(base)
        logger.info("llm_request_start provider=ollama model=%s url=%s prompt_chars=%s system_chars=%s", self.model, url, len(prompt or ""), len(system or ""))
        r = requests.post(url, json=payload, timeout=float(os.getenv("OLLAMA_TIMEOUT_S", "180")), headers=headers)
        r.raise_for_status()
        data = r.json()
        msg = data.get("message", {}) if isinstance(data, dict) else {}
        out = str(msg.get("content", "")).strip()
        logger.info("llm_request_end provider=ollama model=%s output_chars=%s", self.model, len(out))
        return out

    def _chat_openai(self, prompt: str, system: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai não instalado; pip install openai") from e

        if self._openai_client is None:
            self._openai_client = OpenAI()
        messages: List[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        r = self._openai_client.chat.completions.create(model=model, messages=messages)
        return (r.choices[0].message.content or "").strip()


llm = LLMGateway()


def chat_json_object(prompt: str, *, system: str = "") -> dict:
    """Chama o LLM e interpreta a resposta como um único objeto JSON."""
    from backend.core.json_utils import parse_llm_json

    raw = llm.chat(prompt, system)
    return parse_llm_json(raw)
