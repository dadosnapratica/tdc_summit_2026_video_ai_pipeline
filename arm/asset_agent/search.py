from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Sequence

import requests
from dotenv import load_dotenv
from backend.agents.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

from .sources import nasa as nasa_source  # noqa: E402
from .sources import pexels as pexels_source  # noqa: E402
from .sources import pixabay as pixabay_source  # noqa: E402
from .sources import unsplash as unsplash_source  # noqa: E402
from .sources import wikimedia as wikimedia_source  # noqa: E402
from .common import SearchConfig  # noqa: E402


DEFAULT_STYLE_GUIDE = (
    "cinematic documentary, realistic, high detail, 16:9, 1080p, no text, no logos, no watermarks"
)


def _clean_scene_prompt(scene: str) -> str:
    s = (scene or "").strip()
    # Remove prefixo "Scene X:" e style guide comum.
    s = re.sub(r"^\s*scene\s*\d+\s*:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bstyle\s*:\s*.*$", "", s, flags=re.IGNORECASE).strip()
    return s


def _make_query(scene: str, style: str) -> str:
    scene_clean = _clean_scene_prompt(scene)
    style_clean = (style or "").strip()

    # Queries curtas performam melhor em bancos; extraímos termos principais.
    tokens = re.findall(r"[a-zA-Z0-9]+", scene_clean.lower())
    stop = {
        "with",
        "and",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "no",
        "wide",
        "shot",
        "close",
        "up",
        "style",
        "realistic",
        "cinematic",
        "documentary",
        "high",
        "detail",
        "text",
        "logos",
        "watermarks",
        "image",
        "video",
    }
    keywords = [t for t in tokens if t not in stop]
    keywords = keywords[:8] if keywords else tokens[:6]

    # Injeta 1-2 termos do estilo quando úteis (sem exagerar).
    style_tokens = re.findall(r"[a-zA-Z0-9]+", style_clean.lower())
    style_hint = []
    for t in style_tokens:
        # Apenas termos de *estilo* (evitar enviesar nichos como "space"/"nasa").
        if t in ("realistic", "cinematic", "documentary", "photorealistic", "film", "filmic"):
            style_hint.append(t)
        if len(style_hint) >= 2:
            break

    q = " ".join(keywords + style_hint).strip()
    # Fallback neutro (evita puxar para astronomia).
    return q or scene_clean or "stock footage"


def _safe_get(d: Dict[str, Any], path: List[str], default: Any = "") -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", text or "") if t]


def _clean_json_from_llm(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.removeprefix("```json").removeprefix("```").strip()
        if s.endswith("```"):
            s = s.removesuffix("```").strip()
    return s


def _extract_first_json_obj(raw: str) -> str:
    """
    Melhor esforço para extrair um objeto JSON quando o LLM adiciona texto extra.
    Ex.: "Aqui está:\n{...}\n" ou markdown fences.
    """
    s = _clean_json_from_llm(raw)
    if not s:
        return ""
    a = s.find("{")
    b = s.rfind("}")
    if a >= 0 and b > a:
        return s[a : b + 1].strip()
    return s.strip()


def _ollama_chat_json(prompt: str, *, system: str = "") -> Dict[str, Any]:
    base_url = (os.getenv("OLLAMA_BASE_URL") or "http://gpu-server-01:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL") or "llama3"
    url = f"{base_url}/api/chat"
    tok = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip().strip('"')
    headers = {"Authorization": f"Bearer {tok}"} if tok and "/v1/proxy/" in base_url else {}
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.2}}
    # Quando suportado pelo Ollama, força o modelo a retornar JSON válido.
    # (Se a versão não suportar, o campo é ignorado.)
    payload["format"] = "json"

    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=payload, timeout=120, headers=headers)
            r.raise_for_status()
            try:
                data = r.json()
            except json.JSONDecodeError as je:
                snippet = (r.text or "")[:500].replace("\n", " ")
                raise RuntimeError(f"Ollama não devolveu JSON: {je}; body≈{snippet!r}") from je

            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(str(data["error"]))

            msg = data.get("message", {}) if isinstance(data, dict) else {}
            content = str(msg.get("content", "")).strip()
            if not content:
                snippet = json.dumps(data)[:800] if isinstance(data, dict) else str(data)[:800]
                raise RuntimeError(f"resposta sem message.content (model={model}): {snippet}")

            clean = _clean_json_from_llm(content)
            if not clean:
                raise RuntimeError(f"JSON do LLM vazio após limpeza; content≈{content[:400]!r}")
            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                extracted = _extract_first_json_obj(clean)
                if extracted and extracted != clean:
                    return json.loads(extracted)
                # Sem JSON detectável → preservar snippet para debug
                raise RuntimeError(f"LLM não retornou JSON válido; content≈{content[:500]!r}")
        except Exception as e:
            last_err = e
            time.sleep(0.6 * attempt)

    # Inclui tipo do erro para evitar ficar “idêntico” a logs antigos.
    et = type(last_err).__name__ if last_err else "None"
    raise RuntimeError(f"Falha ao chamar Ollama em {url} (model={model}) [{et}]: {last_err}")


PreferMode = str


def _normalize_prefer(raw: str) -> PreferMode:
    v = (raw or "").strip().lower()
    if v == "any":
        v = "all"
    if v in ("video_first", "image_first", "all", "video", "image"):
        return v
    # Compat: valores antigos
    if v in ("videos_first", "video-first"):
        return "video_first"
    if v in ("images_first", "image-first"):
        return "image_first"
    return "all"


def _score_asset(asset: Dict[str, Any], *, query: str, scene_prompt: str, style_guide: str, prefer: PreferMode) -> float:
    """
    Score heurístico simples:
    - overlap de tokens entre query/scene e metadados do asset (quando disponíveis)
    - bônus por preview
    - bônus por tipo preferido
    """
    prefer = _normalize_prefer(prefer)
    asset_type = str(asset.get("asset_type", "")).lower()
    # Modos "hard": filtra por tipo na seleção (aqui só penaliza forte).
    if prefer in ("image", "video") and asset_type and asset_type != prefer:
        type_penalty = -2.0
    else:
        type_penalty = 0.0

    text = " ".join(
        [
            str(asset.get("url", "")),
            str(asset.get("preview_url", "")),
            str(asset.get("author", "")),
            str(asset.get("license", "")),
            str(asset.get("text", "")),
            str(asset.get("tags", "")),
        ]
    )
    a_tokens = set(_tokenize(text))
    q_tokens = set(_tokenize(query))
    s_tokens = set(_tokenize(_clean_scene_prompt(scene_prompt)))
    style_tokens = set(_tokenize(style_guide))

    overlap = len(a_tokens & q_tokens) * 1.2 + len(a_tokens & s_tokens) * 0.8
    style_overlap = len(a_tokens & style_tokens) * 0.2

    preview_bonus = 0.2 if str(asset.get("preview_url", "")).strip() else 0.0
    source_bonus = 0.1 if str(asset.get("source", "")).strip() else 0.0

    # Preferências:
    # - all: neutro (só relevância/heurística; sem viés imagem vs vídeo)
    # - video_first / image_first: bônus leve ao tipo
    # - video/image: filtro duro (penalty acima)
    type_bonus = 0.0
    if prefer == "video_first":
        type_bonus += 0.35 if asset_type == "video" else (-0.05 if asset_type == "image" else 0.0)
    elif prefer == "image_first":
        type_bonus += 0.25 if asset_type == "image" else (-0.05 if asset_type == "video" else 0.0)

    # Penaliza aspect ratios muito longe de 16:9 quando a fonte fornece dimensões.
    # "16:9" no style_guide é só uma dica textual; enforcement precisa de metadados.
    aspect_penalty = 0.0
    try:
        w = asset.get("width")
        h = asset.get("height")
        wf = float(w) if w is not None else 0.0
        hf = float(h) if h is not None else 0.0
        if wf > 0 and hf > 0:
            r = wf / hf
            target = 16.0 / 9.0
            tol = float(os.getenv("IMAGE_RESEARCH_ASPECT_TOLERANCE", "0.12"))  # ~±12%
            if abs(r - target) > tol:
                aspect_penalty = -min(1.25, abs(r - target) * 1.2)
    except Exception:
        aspect_penalty = 0.0

    return overlap + style_overlap + preview_bonus + source_bonus + type_bonus + type_penalty + aspect_penalty


def select_best_asset(
    assets: List[Dict[str, Any]],
    *,
    query: str,
    scene_prompt: str,
    style_guide: str,
    prefer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retorna {"selected_idx": int|None, "selected_asset": dict|None, "ranker": "..."}.
    Ranker:
      - heuristic (default)
      - ollama (opcional) se IMAGE_RESEARCH_RANKER=ollama
    """
    prefer_mode = _normalize_prefer(
        prefer
        or (os.getenv("ASSET_RESEARCH_PREFERENCE") or os.getenv("IMAGE_RESEARCH_PREFER") or "video_first")
    )
    ranker = (os.getenv("IMAGE_RESEARCH_RANKER") or "heuristic").strip().lower()

    if not assets:
        return {"selected_idx": None, "selected_asset": None, "ranker": ranker}

    # Em modos hard, reduza o universo antes do ranker (mantém fallback se lista ficar vazia).
    if prefer_mode in ("image", "video"):
        filtered = [a for a in assets if str(a.get("asset_type", "")).lower() == prefer_mode]
        if filtered:
            assets = filtered

    if ranker == "ollama":
        try:
            # envia um subconjunto pequeno e normalizado
            items = []
            for i, a in enumerate(assets[:25]):
                items.append(
                    {
                        "id": i,
                        "asset_type": a.get("asset_type"),
                        "source": a.get("source"),
                        "license": a.get("license"),
                        "url": a.get("url"),
                        "preview_url": a.get("preview_url", ""),
                        "text": a.get("text", "") or a.get("tags", ""),
                    }
                )

            system = (
                load_prompt("asset_agent/asset_curation").strip()
                or "Você é um curador de assets visuais para vídeos. Retorne APENAS JSON."
            )
            mode_hint = {
                "video_first": "Prefira vídeos quando houver empate de relevância; use imagem só se for claramente melhor.",
                "image_first": "Prefira imagens quando houver empate; use vídeo só se for claramente melhor.",
                "all": "Considere imagens e vídeos em pé de igualdade; escolha pelo melhor encaixe na cena (sem preferir tipo).",
                "video": "Apenas vídeos na lista.",
                "image": "Apenas imagens na lista.",
            }.get(prefer_mode, "")
            prompt = (
                f"Scene prompt: {scene_prompt}\n"
                f"Style guide: {style_guide}\n"
                f"Modo de preferência: {prefer_mode}. {mode_hint}\n"
                f"Query: {query}\n\n"
                "Assets (JSON):\n"
                f"{json.dumps(items, ensure_ascii=False)}\n\n"
                "Retorne APENAS este JSON:\n"
                '{"selected_id": <int>, "reason": "<curto>"}'
            )
            resp = _ollama_chat_json(prompt, system=system)
            sel = resp.get("selected_id")
            if isinstance(sel, int) and 0 <= sel < len(assets[:25]):
                return {
                    "selected_idx": sel,
                    "selected_asset": assets[sel],
                    "ranker": "ollama",
                    "reason": str(resp.get("reason", "")).strip(),
                }
        except Exception as e:
            logger.warning("[ranker:ollama] falhou, fallback heuristic: %s", e)

    # heuristic (default/fallback)
    scored = [
        (
            i,
            _score_asset(a, query=query, scene_prompt=scene_prompt, style_guide=style_guide, prefer=prefer_mode),
        )
        for i, a in enumerate(assets)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_i = scored[0][0]
    return {"selected_idx": best_i, "selected_asset": assets[best_i], "ranker": "heuristic"}


def _search_sources(query: str, cfg: SearchConfig, enabled: Sequence[str]) -> List[Dict[str, Any]]:
    assets: List[Dict[str, Any]] = []
    if "pexels" in enabled:
        assets.extend(pexels_source.search(query, cfg))
    if "pixabay" in enabled:
        assets.extend(pixabay_source.search(query, cfg))
    if "unsplash" in enabled:
        assets.extend(unsplash_source.search(query, cfg))
    if "nasa" in enabled:
        assets.extend(nasa_source.search(query, cfg))
    if "wikimedia" in enabled:
        assets.extend(wikimedia_source.search(query, cfg))
    return assets


def search_assets_for_scene(
    scene_prompt: str,
    *,
    style_guide: str = DEFAULT_STYLE_GUIDE,
    prefer: Optional[str] = None,
    cfg: Optional[SearchConfig] = None,
) -> Dict[str, Any]:
    cfg = cfg or SearchConfig()
    query = _make_query(scene_prompt, style_guide)

    enabled_raw = (os.getenv("IMAGE_RESEARCH_SOURCES") or "").strip()
    if enabled_raw:
        enabled = {s.strip().lower() for s in enabled_raw.split(",") if s.strip()}
    else:
        enabled = {"pexels", "pixabay", "unsplash", "nasa", "wikimedia"}

    assets = _search_sources(query, cfg, sorted(enabled))
    selection = select_best_asset(
        assets,
        query=query,
        scene_prompt=scene_prompt,
        style_guide=style_guide,
        prefer=prefer,
    )

    return {
        "scene_prompt": scene_prompt,
        "style_guide": style_guide,
        "query": query,
        "enabled_sources": sorted(enabled),
        "assets": assets,
        **selection,
    }


def main() -> None:
    # Por conveniência: `.env` na raiz de `workshop/` (ou variáveis já no ambiente).
    load_dotenv()
    if not (os.getenv("PEXELS_API_KEY") or os.getenv("PIXABAY_API_KEY") or os.getenv("UNSPLASH_ACCESS_KEY")):
        load_dotenv(
            dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        )
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True, help="prompt de cena (ex: 'Scene 1: ...')")
    parser.add_argument("--style", default=DEFAULT_STYLE_GUIDE, help="guia de estilo (opcional)")
    parser.add_argument("--per-source", type=int, default=5, help="quantidade por fonte (aprox.)")
    parser.add_argument("--demo", action="store_true", help="usa assets fake para testar o ranker")
    parser.add_argument("--json", action="store_true", help="imprime JSON")
    args = parser.parse_args()

    cfg = SearchConfig(per_source=max(1, int(args.per_source)))
    if args.demo:
        query = _make_query(args.scene, args.style)
        fake_assets = [
            {
                "asset_type": "image",
                "url": "https://example.com/space/black-hole-artist-impression",
                "preview_url": "https://example.com/prev1.jpg",
                "source": "pexels",
                "license": "Pexels License (free to use)",
                "author": "A. Photographer",
                "text": "artist impression black hole accretion disk",
                "query": query,
            },
            {
                "asset_type": "image",
                "url": "https://example.com/cats/cute-cat",
                "preview_url": "https://example.com/prev2.jpg",
                "source": "pexels",
                "license": "Pexels License (free to use)",
                "author": "B. Photographer",
                "text": "cute cat portrait",
                "query": query,
            },
            {
                "asset_type": "video",
                "url": "https://example.com/space/nebula-video",
                "preview_url": "https://example.com/prev3.jpg",
                "source": "pexels",
                "license": "Pexels License (free to use)",
                "author": "C. Creator",
                "text": "space nebula timelapse",
                "query": query,
            },
        ]
        sel = select_best_asset(fake_assets, query=query, scene_prompt=args.scene, style_guide=args.style)
        result = {
            "scene_prompt": args.scene,
            "style_guide": args.style,
            "query": query,
            "enabled_sources": ["demo"],
            "assets": fake_assets,
            **sel,
        }
    else:
        result = search_assets_for_scene(args.scene, style_guide=args.style, cfg=cfg)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Scene: {result['scene_prompt']}")
    print(f"Query:  {result['query']}\n")
    if result.get("selected_asset"):
        sa = result["selected_asset"]
        print(
            f"Selected: [{sa.get('source')}] {sa.get('asset_type')} — {sa.get('license')}\n"
            f"    {sa.get('url')}\n"
        )
    for i, a in enumerate(result["assets"], start=1):
        print(
            f"{i:02d}. [{a.get('source')}] {a.get('asset_type')} — {a.get('license')}\n"
            f"    {a.get('url')}\n"
        )


if __name__ == "__main__":
    main()

