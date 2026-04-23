from __future__ import annotations

import os
import json
import re
import secrets
import tempfile
import logging
import time
import traceback
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Dict, Optional

from pathlib import Path
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response as StarletteResponse

# Evitar vazar detalhes sensíveis (paths, tokens, stack) em respostas HTTP.
logger = logging.getLogger(__name__)

from workshop.backend.dotenv_loader import load_workshop_dotenv

load_workshop_dotenv(here=Path(__file__).resolve())

_EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]

from workshop.backend.core.correlation import set_correlation_id  # noqa: E402
from .logging_setup import configure_logging  # noqa: E402

from workshop.arm.asset_agent.search import DEFAULT_STYLE_GUIDE as IMAGE_DEFAULT_STYLE_GUIDE  # noqa: E402
from workshop.arm.asset_agent.search import SearchConfig, search_assets_for_scene  # noqa: E402
from workshop.arm.research_agent.youtube_trends_research import build_research_pack  # noqa: E402
from workshop.arm.script_agent.generate import generate_script, suggest_angles  # noqa: E402
from workshop.arm.composer_agent.lab import run_composer_lab  # noqa: E402
from workshop.arm.tts_agent.lab import run_tts_lab  # noqa: E402
from workshop.arm.visual_agent.lab import run_visual_batch, run_visual_lab  # noqa: E402
from workshop.backend.agents.metadata_agent import metadata_agent  # noqa: E402
from workshop.backend.agents.thumbnail_card_agent import thumbnail_card_agent  # noqa: E402
from workshop.backend.core.state import VideoState  # noqa: E402
from workshop.backend.core.tts_provider_config import (  # noqa: E402
    tts_provider_effective,
    tts_providers_enabled,
)

from .api_schemas import (  # noqa: E402
    AnglesResponse,
    AsrLabRequest,
    ComposerLabRequest,
    LabSyncComposeRequest,
    GenerateRequest,
    HealthResponse,
    ImageSearchRequest,
    LivenessResponse,
    MetadataLabRequest,
    PublishGrowthPreviewRequest,
    ThumbnailLabRequest,
    ResearchRequest,
    TtsLabRequest,
    VisualBatchRequest,
    VisualLabRequest,
    YoutubeUploadLabRequest,
)
from .health_checks import build_health_report  # noqa: E402
from .piper_voice_list import build_piper_model_options, resolve_piper_model_for_request  # noqa: E402

_BFF_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSHOP_ROOT = os.path.abspath(os.path.join(_BFF_DIR, ".."))
WEB_DIR = os.path.join(_WORKSHOP_ROOT, "web")
_DEFAULT_YOUTUBE_AUTH_DIR = os.path.join(_WORKSHOP_ROOT, "config", "youtube_auth")
# Sobrescreve com path absoluto se tokens estiverem noutro disco/NFS.
YOUTUBE_AUTH_DIR = (os.getenv("YOUTUBE_AUTH_DIR") or "").strip() or _DEFAULT_YOUTUBE_AUTH_DIR
ACCOUNTS_DIR = os.path.join(YOUTUBE_AUTH_DIR, "accounts")
CHANNELS_DIR = os.path.join(YOUTUBE_AUTH_DIR, "channels")
OAUTH_STATES_DIR = os.path.join(YOUTUBE_AUTH_DIR, "oauth_states")
YOUTUBE_OAUTH_SCOPES = [
    # Listar canais do usuário (mine=True)
    "https://www.googleapis.com/auth/youtube.readonly",
    # Publicação (fase seguinte) — e evita erro de “scope changed” quando a conta já concedeu upload antes
    "https://www.googleapis.com/auth/youtube.upload",
    # Identidade do usuário (para nomear token por conta e suportar multiusuário)
    "openid",
    # Nota: o Google pode retornar `userinfo.email` em vez de `email`; pedimos o mais específico.
    "https://www.googleapis.com/auth/userinfo.email",
]

APP_DESCRIPTION = """
API do laboratório **IA VideoStudio** (Ideias Factory).

Módulos expostos (alinhados aos agentes de produção):
- **script_agent** (lab) — geração de roteiro e cenas; pode usar Ollama (`OLLAMA_BASE_URL`). Rota: `/api/script_agent/generate`.
- **research_agent** — vídeos populares (YouTube Data API) + sinais Google Trends (`pytrends`). Rota: `/api/research_agent/youtube_trends`.
- **asset_agent** (lab) — curadoria multi-fonte (Pexels, Pixabay, Unsplash conforme env). Rota: `/api/asset_agent/search`.
- **visual_agent** (lab) — um clipe a partir de uma imagem (ComfyUI quando configurado; senão ffmpeg). Rotas: `/api/visual_agent/preview`, `/api/visual_agent/batch`, `/api/visual_agent/result/{token}`.
- **tts_agent** (lab) — narração WAV (`workshop.backend.agents.tts_agent`). Rota: `/api/tts_agent/preview`; áudio em `/api/lab/job/{token}/narration.wav`.
- **composer_agent** (lab) — `final.mp4` a partir de clipes + áudio (`agents.composer_agent`). Rota: `/api/composer_agent/preview`; vídeo em `/api/lab/job/{token}/final.mp4`.
- **Sincronismo avançado** — timeline dinâmica + recomposição (`video_compose_experiments`). Rota: `POST /api/lab/sync_compose`; saída `final_synced.mp4` em `/api/lab/job/{token}/final_synced.mp4` (requer ASR + `script_lab.txt` gravado no TTS).

Os passos partilham um ``job_token`` devolvido pelo primeiro pedido (ou enviado explicitamente).

**Erros comuns**
- `422` — corpo ou query inválidos (validação Pydantic).
- `500` — falha não tratada no handler (ver logs do uvicorn).

Variáveis de ambiente relevantes: `YOUTUBE_API_KEY`, `OLLAMA_BASE_URL`, `PEXELS_API_KEY`, etc.
"""


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    from workshop.backend.config_validation import validate_workshop_configuration

    report = validate_workshop_configuration()
    logger.warning("workshop_config_validation %s", json.dumps(report, ensure_ascii=False))
    for item in report.get("items", []):
        if item.get("severity") != "ok":
            logger.warning(
                "config_validation [%s] %s — %s",
                item.get("id"),
                item.get("severity"),
                item.get("message"),
            )
    strict = (os.getenv("WORKSHOP_CONFIG_STRICT") or "").strip().lower() in ("1", "true", "yes")
    if strict and report.get("has_errors"):
        raise RuntimeError("WORKSHOP_CONFIG_STRICT: erros na validação de configuração (ver logs)")
    yield


app = FastAPI(
    title="IA VideoStudio — Ideias Factory",
    version="0.2.0",
    description=APP_DESCRIPTION,
    lifespan=_lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_tags=[
        {"name": "script_agent", "description": "Geração de roteiro, textos e cenas (lab; espelha agents.script_agent)."},
        {"name": "research_agent", "description": "Research YouTube + Google Trends (lab; espelha agents.research_agent)."},
        {"name": "asset_agent", "description": "Busca de assets por cena (lab; espelha agents.asset_agent)."},
        {"name": "visual_agent", "description": "Clipes a partir de imagens (lab; espelha agents.visual_agent / ComfyUI)."},
        {"name": "tts_agent", "description": "Narração TTS (lab; espelha workshop.backend.agents.tts_agent)."},
        {"name": "composer_agent", "description": "Composição final ffmpeg (lab; espelha agents.composer_agent)."},
        {"name": "lab_job", "description": "Sessão partilhada (paths NFS/temp) para TTS + visual + composer."},
        {"name": "youtube", "description": "OAuth e dados da conta YouTube do usuário (lab)."},
        {"name": "sistema", "description": "Health e metadados."},
    ],
)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.middleware("http")
async def _no_cache_static_html(request: Request, call_next):
    """
    Evita que o browser fique preso em versões antigas do HTML da SPA.
    JS/CSS já usam cache-buster `?v=...`, mas o `index.html` pode ficar cacheado.
    """
    resp = await call_next(request)
    path = (request.url.path or "").lower()
    if path.startswith("/static/") and path.endswith(".html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.middleware("http")
async def _correlation_and_request_logs(request: Request, call_next):
    """
    - correlation id: vindo da UI via X-Correlation-Id (ou gerado)
    - log start/end com ip, method, path, status, duração
    """
    cid = (request.headers.get("x-correlation-id") or request.headers.get("X-Correlation-Id") or "").strip()
    if not cid:
        # fallback simples (sem depender de libs): token curto + timestamp
        cid = f"cid_srv_{secrets.token_hex(8)}_{int(time.time())}"
    set_correlation_id(cid)

    ip = getattr(request.client, "host", "") or "-"
    method = (request.method or "").upper()
    path = request.url.path
    t0 = time.perf_counter()
    logger.info("request_start ip=%s method=%s path=%s", ip, method, path)
    try:
        resp = await call_next(request)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        logger.info("request_end ip=%s method=%s path=%s status=%s duration_ms=%.1f", ip, method, path, resp.status_code, dt_ms)
        return resp
    except Exception:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        logger.exception("request_error ip=%s method=%s path=%s duration_ms=%.1f", ip, method, path, dt_ms)
        raise


@app.middleware("http")
async def _trace_debug_log(request: Request, call_next):
    """
    Debug forense (sensível): request/response + exceções, em arquivo JSONL.
    Habilitar via DEBUG_TRACE_LOG=1.
    """
    if (os.getenv("DEBUG_TRACE_LOG") or "").strip().lower() not in ("1", "true", "yes"):
        return await call_next(request)

    # só API (evita vazar conteúdo de static)
    path = request.url.path or ""
    if not path.startswith("/api/") and not path.startswith("/health"):
        return await call_next(request)

    trace_logger = logging.getLogger("lab_trace")
    ip = getattr(request.client, "host", "") or "-"
    method = (request.method or "").upper()
    q = str(request.url.query or "")
    t0 = time.perf_counter()

    # body (limitado)
    max_body = int(os.getenv("DEBUG_TRACE_MAX_BODY_BYTES") or "65536")
    body_bytes = b""
    try:
        body_bytes = await request.body()
    except Exception:
        body_bytes = b""
    if max_body > 0 and len(body_bytes) > max_body:
        body_bytes = body_bytes[:max_body] + b"...(truncated)"
    try:
        body_text = body_bytes.decode("utf-8", errors="replace")
    except Exception:
        body_text = repr(body_bytes)

    trace_logger.debug(
        json.dumps(
            {
                "event": "http_request_start",
                "ip": ip,
                "method": method,
                "path": path,
                "query": q,
                "headers": {
                    # whitelist mínima
                    "user-agent": request.headers.get("user-agent", ""),
                    "content-type": request.headers.get("content-type", ""),
                    "x-correlation-id": request.headers.get("x-correlation-id", ""),
                },
                "body": body_text,
            },
            ensure_ascii=False,
        )
    )

    try:
        resp = await call_next(request)
    except Exception as e:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        trace_logger.debug(
            json.dumps(
                {
                    "event": "http_request_error",
                    "ip": ip,
                    "method": method,
                    "path": path,
                    "duration_ms": round(dt_ms, 1),
                    "error": repr(e),
                    "traceback": traceback.format_exc()[:20000],
                },
                ensure_ascii=False,
            )
        )
        raise

    # Response body (limitado): capturar JSON/texto sem quebrar o cliente depois do consume do stream.
    # Nota: cada @app.middleware("http") usa Starlette BaseHTTPMiddleware, que substitui a resposta real
    # por starlette.middleware.base._StreamingResponse — tem body_iterator e não preenche .body; também
    # não é isinstance(..., StreamingResponse) da starlette.responses. Por isso detetamos stream via
    # body_iterator, não só via tipo.
    dt_ms = (time.perf_counter() - t0) * 1000.0
    resp_body_text: Optional[str] = None
    ctype_l = ""
    try:
        ctype = (resp.headers.get("content-type", "") if hasattr(resp, "headers") else "") or ""
        ctype_l = ctype.lower()
        is_textual = ("application/json" in ctype_l) or ctype_l.startswith("text/")

        body_iter = getattr(resp, "body_iterator", None)
        # BaseHTTPMiddleware devolve _StreamingResponse (tem body_iterator, sem .body; não é
        # starlette.responses.StreamingResponse). Priorizar iterator quando existir.
        if is_textual and body_iter is not None:
            collected = bytearray()
            chunks: List[bytes] = []
            async for chunk in body_iter:  # type: ignore[attr-defined]
                if not isinstance(chunk, (bytes, bytearray)):
                    chunk = str(chunk).encode("utf-8", errors="replace")
                bch = bytes(chunk)
                chunks.append(bch)
                if max_body > 0 and len(collected) < max_body:
                    take = max_body - len(collected)
                    collected.extend(bch[:take])
            if max_body > 0 and len(collected) >= max_body:
                collected.extend(b"...(truncated)")
            resp_body_text = bytes(collected).decode("utf-8", errors="replace") if collected else ""

            headers = dict(resp.headers) if hasattr(resp, "headers") else {}
            headers.pop("content-length", None)
            media_type = getattr(resp, "media_type", None) or headers.get("content-type", None)
            resp = StarletteResponse(
                content=b"".join(chunks),
                status_code=getattr(resp, "status_code", 200),
                headers=headers,
                media_type=media_type,
                background=getattr(resp, "background", None),
            )
        elif isinstance(resp, StarletteResponse) and is_textual:
            b = bytes(getattr(resp, "body", b"") or b"")
            if max_body > 0 and len(b) > max_body:
                b = b[:max_body] + b"...(truncated)"
            resp_body_text = b.decode("utf-8", errors="replace")
    except Exception:
        resp_body_text = None

    response_body_log: Any = resp_body_text
    if resp_body_text is not None and "application/json" in ctype_l:
        try:
            response_body_log = json.loads(resp_body_text.strip())
        except json.JSONDecodeError:
            response_body_log = resp_body_text

    trace_logger.debug(
        json.dumps(
            {
                "event": "http_request_end",
                "ip": ip,
                "method": method,
                "path": path,
                "status": getattr(resp, "status_code", None),
                "duration_ms": round(dt_ms, 1),
                # JSON MIME: objeto/array no trace; falha de parse ou texto cru mantém string
                "response_body": response_body_log,
                "response_headers": {
                    "content-type": resp.headers.get("content-type", "") if hasattr(resp, "headers") else "",
                },
            },
            ensure_ascii=False,
        )
    )
    return resp


@contextmanager
def _temp_env(updates: Dict[str, Optional[str]]):
    old: Dict[str, Optional[str]] = {}
    for k, v in updates.items():
        old[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@app.get("/swagger", include_in_schema=False)
def swagger_ui():
    """Swagger UI (substitui o `/docs` padrão do FastAPI)."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="IA VideoStudio — API")


@app.get("/redoc", include_in_schema=False)
def redoc_ui():
    return get_redoc_html(openapi_url="/openapi.json", title="IA VideoStudio — API")


@app.get("/", tags=["sistema"], summary="Interface web (SPA)")
def index():
    """Redireciona para o ficheiro servido em `/static` (caminhos relativos no HTML)."""
    return RedirectResponse(url="/static/index.html", status_code=302)


@app.get("/terms.html", include_in_schema=False)
def terms_html():
    """Atalho compatível com links antigos (serve via /static)."""
    return RedirectResponse(url="/static/terms.html", status_code=302)


@app.get("/privacy.html", include_in_schema=False)
def privacy_html():
    """Atalho compatível com links antigos (serve via /static)."""
    return RedirectResponse(url="/static/privacy.html", status_code=302)


@app.get(
    "/health/live",
    response_model=LivenessResponse,
    tags=["sistema"],
    summary="Liveness",
    description="Resposta mínima para balanceadores / Kubernetes (não consulta Ollama).",
)
def health_live():
    return {"status": "ok"}


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["sistema"],
    summary="Readiness / dependências",
    description=(
        "Verifica Ollama (HTTP), import do pytrends, presença de `YOUTUBE_API_KEY` "
        "e ao menos uma chave de image search. Não expõe segredos."
    ),
)
def health_ready() -> Dict[str, Any]:
    return build_health_report()


@app.get(
    "/api/angles",
    response_model=AnglesResponse,
    tags=["script_agent"],
    summary="Sugerir ângulos para um tema",
    responses={422: {"description": "Parâmetros de query inválidos"}},
)
def api_angles(tema: str = "", use_ollama: Optional[bool] = None):
    updates: Dict[str, Optional[str]] = {}
    if use_ollama is True:
        updates["USE_OLLAMA"] = "1"
    elif use_ollama is False:
        updates["USE_OLLAMA"] = "0"

    with _temp_env(updates) if updates else _temp_env({}):
        return {"tema": tema, "angles": suggest_angles(tema)}


@app.post(
    "/api/script_agent/generate",
    tags=["script_agent"],
    summary="Gerar roteiro completo",
    response_description="Roteiro base, textos, cenas e metadados do gerador.",
    responses={
        422: {"description": "JSON de entrada inválido"},
        200: {
            "description": "Payload do gerador (script_agent lab)",
            "content": {
                "application/json": {
                    "example": {
                        "roteiro_base": "...",
                        "textos": [],
                        "scenes": [{"idx": 0, "prompt": "..."}],
                    }
                }
            },
        },
    },
)
def api_generate(req: GenerateRequest) -> Dict[str, Any]:
    updates: Dict[str, Optional[str]] = {}
    if req.use_ollama is True:
        updates["USE_OLLAMA"] = "1"
    elif req.use_ollama is False:
        updates["USE_OLLAMA"] = "0"

    with _temp_env(updates) if updates else _temp_env({}):
        return generate_script(
            req.tema,
            req.angulo,
            youtube_context=req.youtube_context,
            duration_tier=req.duration_tier,
            target_narration_seconds=(
                int(round(float(req.target_narration_minutes) * 60))
                if getattr(req, "duration_tier", None) == "custom" and req.target_narration_minutes is not None
                else None
            ),
        )


@app.post(
    "/api/research_agent/youtube_trends",
    tags=["research_agent"],
    summary="Research: YouTube + Trends",
    response_description="trends (pytrends), vídeos, trends_panel e sugestões ranqueadas.",
    responses={
        422: {"description": "Corpo inválido"},
        200: {
            "description": "Pacote de research",
            "content": {
                "application/json": {
                    "example": {
                        "keyword": "astronomia",
                        "trends_panel": {"seed_keyword": "astronomia", "related_rising": []},
                        "video_suggestions": [],
                    }
                }
            },
        },
    },
)
def api_research(req: ResearchRequest) -> Dict[str, Any]:
    return build_research_pack(
        req.keyword.strip(),
        region=req.region,
        category_id=req.category_id,
        youtube_n=int(req.youtube_n),
        trends_days=int(req.trends_days),
    )


@app.post(
    "/api/asset_agent/search",
    tags=["asset_agent"],
    summary="Buscar assets para uma cena",
    response_description="Lista de candidatos, escolha e justificativa.",
    responses={
        422: {"description": "Corpo inválido"},
        200: {
            "description": "Resultado da busca",
            "content": {
                "application/json": {
                    "example": {
                        "assets": [],
                        "selected_idx": 0,
                        "selected_asset": None,
                        "reason": "",
                    }
                }
            },
        },
    },
)
def api_image_search(req: ImageSearchRequest) -> Dict[str, Any]:
    cfg = SearchConfig(per_source=int(req.per_source))
    # Prioridade do style guide:
    # - UI (req.style)
    # - env ASSET_DEFAULT_STYLE_GUIDE (novo)
    # - env IMAGE_RESEARCH_STYLE_GUIDE (legado)
    # - fallback DEFAULT_STYLE_GUIDE
    style = (
        req.style.strip()
        or os.getenv("ASSET_DEFAULT_STYLE_GUIDE", "").strip()
        or os.getenv("IMAGE_RESEARCH_STYLE_GUIDE", "").strip()
        or IMAGE_DEFAULT_STYLE_GUIDE
    )
    # Preferência: UI (se enviado) → ASSET_RESEARCH_PREFERENCE → legado IMAGE_RESEARCH_PREFER → video_first
    if req.prefer is not None:
        prefer = str(req.prefer).strip()
    else:
        prefer = (
            (os.getenv("ASSET_RESEARCH_PREFERENCE") or os.getenv("IMAGE_RESEARCH_PREFER") or "video_first").strip()
        )
    return search_assets_for_scene(req.scene, style_guide=style, prefer=prefer, cfg=cfg)


_VISUAL_LAB_RESULTS: Dict[str, str] = {}


@app.post(
    "/api/visual_agent/preview",
    tags=["visual_agent"],
    summary="Gerar um clipe (lab) a partir de uma imagem",
    response_description="Metadados do run; use result_id com GET /api/visual_agent/result/{token} para descarregar o mp4.",
)
def api_visual_preview(req: VisualLabRequest) -> Dict[str, Any]:
    """
    Executa o mesmo fluxo que ``agents.visual_agent`` para um único asset.

    O BFF precisa de ``ffmpeg`` (fallback). Para ComfyUI: ``COMFYUI_INPUT_METHOD=upload``
    (HTTP) ou ``copy`` com ``COMFYUI_INPUT_DIR`` no mesmo filesystem/NFS que o servidor ComfyUI.
    """
    out = run_visual_lab(
        req.image.strip(),
        scene_idx=int(req.scene_idx),
        visual_use_comfy=req.use_comfy,
    )
    token = ""
    clip_path = (out.get("clip_path") or "").strip()
    if out.get("ok") and clip_path and os.path.isfile(clip_path):
        token = secrets.token_urlsafe(16)
        _VISUAL_LAB_RESULTS[token] = os.path.abspath(clip_path)
    return {
        **out,
        "result_id": token,
        "result_url": f"/api/visual_agent/result/{token}" if token else "",
    }


@app.get(
    "/api/visual_agent/result/{token}",
    tags=["visual_agent"],
    summary="Descarregar mp4 gerado pelo preview",
    response_class=FileResponse,
)
def api_visual_result(token: str):
    path = _VISUAL_LAB_RESULTS.get(token)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="resultado expirado ou desconhecido")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename="visual_lab_clip.mp4",
        headers={"Cache-Control": "no-store"},
    )


_LAB_JOB_DIRS: Dict[str, str] = {}


def _lab_jobs_base_dir() -> str:
    base = (os.getenv("PIPELINE_JOBS_PATH") or "").strip()
    if base:
        return os.path.abspath(base)
    # fallback: diretórios temporários (não persistentes)
    return ""


def _is_safe_job_token(t: str) -> bool:
    # token_urlsafe usa [A-Za-z0-9_-]; manter mesma regra para evitar path traversal
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{8,64}", t or ""))


def _write_thumbnail_logo_from_data_url(job_path: str, data_url: str) -> str:
    """Decodifica ``data:image/...;base64,...`` e grava no job; devolve path absoluto ou ``\"\"``."""
    raw = (data_url or "").strip()
    if not raw.startswith("data:") or "," not in raw:
        return ""
    try:
        import base64

        head, _, b64part = raw.partition(",")
        blob = base64.b64decode(b64part, validate=False)
        if not blob:
            return ""
        lh = head.lower()
        ext = ".png"
        if "jpeg" in lh or "jpg" in lh:
            ext = ".jpg"
        elif "webp" in lh:
            ext = ".webp"
        elif "gif" in lh:
            ext = ".gif"
        dest = os.path.join(job_path, f"thumbnail_lab_logo{ext}")
        with open(dest, "wb") as f:
            f.write(blob)
        return dest if os.path.isfile(dest) else ""
    except Exception as e:
        logger.warning("[lab] logo_data_url inválido ou escrita falhou: %s", e)
        return ""


def _resolve_lab_job(job_token: Optional[str]) -> tuple[str, str]:
    """Cria ou reutiliza um diretório de job partilhado entre TTS, visual e composer."""
    t = (job_token or "").strip()
    base = _lab_jobs_base_dir()

    # Reuso (mesmo processo)
    if t and t in _LAB_JOB_DIRS:
        return t, _LAB_JOB_DIRS[t]

    # Reuso persistente (se PIPELINE_JOBS_PATH estiver ativo)
    if t and base and _is_safe_job_token(t):
        path = os.path.join(base, t)
        os.makedirs(os.path.join(path, "assets"), exist_ok=True)
        os.makedirs(os.path.join(path, "clips"), exist_ok=True)
        _LAB_JOB_DIRS[t] = path
        return t, path

    # Cria novo token + diretório
    new_tok = secrets.token_urlsafe(12)
    if base:
        path = os.path.join(base, new_tok)
        os.makedirs(os.path.join(path, "assets"), exist_ok=True)
        os.makedirs(os.path.join(path, "clips"), exist_ok=True)
    else:
        path = os.path.abspath(tempfile.mkdtemp(prefix="ihl_lab_job_"))
        os.makedirs(os.path.join(path, "assets"), exist_ok=True)
        os.makedirs(os.path.join(path, "clips"), exist_ok=True)
    _LAB_JOB_DIRS[new_tok] = path
    return new_tok, path


@app.post(
    "/api/tts_agent/preview",
    tags=["tts_agent"],
    summary="Gerar narração WAV (lab)",
)
def api_tts_preview(req: TtsLabRequest) -> Dict[str, Any]:
    token, path = _resolve_lab_job(req.job_token)
    updates: Dict[str, Optional[str]] = {}
    if req.kokoro_voice:
        updates["KOKORO_VOICE"] = req.kokoro_voice
    if req.kokoro_lang:
        updates["KOKORO_LANG"] = req.kokoro_lang
    if req.kokoro_speed is not None:
        updates["KOKORO_SPEED"] = str(req.kokoro_speed)

    enabled = tts_providers_enabled()
    req_prov = (req.provider or "").strip().lower()
    if req_prov:
        if req_prov not in enabled:
            raise HTTPException(
                status_code=422,
                detail=f"provider não habilitado: {req_prov!r} (TTS_PROVIDER permite: {', '.join(enabled)})",
            )
        prov_eff = req_prov
    else:
        prov_eff = tts_provider_effective()
    updates["TTS_PROVIDER"] = prov_eff

    if req.piper_model and prov_eff != "piper":
        raise HTTPException(
            status_code=422,
            detail="piper_model só pode ser usado com provider=piper (ou motor efetivo piper via TTS_PROVIDER / TTS_PROVIDER_DEFAULT).",
        )
    if req.piper_model and prov_eff == "piper":
        try:
            updates["PIPER_MODEL"] = resolve_piper_model_for_request(req.piper_model)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    with _temp_env(updates) if updates else _temp_env({}):
        out = run_tts_lab(req.script, path)
    narration_url = ""
    if out.get("ok") and (out.get("audio_path") or "").strip():
        narration_url = f"/api/lab/job/{token}/narration.wav"
    return {**out, "job_token": token, "narration_url": narration_url}


@app.get(
    "/api/tts_agent/options",
    tags=["tts_agent"],
    summary="Listar opções de TTS (vozes/idiomas) detectadas no servidor",
)
def api_tts_options() -> Dict[str, Any]:
    """
    UI helper: devolve opções conhecidas + config atual via env.
    Não tenta enumerar vozes Piper automaticamente.
    """
    # Kokoro-82M VOICES.md (subset útil para PT-BR)
    kokoro_ptbr_voices = ["pf_dora", "pm_alex", "pm_santa"]
    kokoro_langs = ["pt-br", "en-us", "en-gb", "es", "fr-fr", "it", "hi", "ja", "zh"]

    kokoro_available = False
    try:
        import kokoro_onnx  # type: ignore  # noqa: F401
        import numpy  # type: ignore  # noqa: F401

        kokoro_available = True
    except Exception:
        kokoro_available = False

    piper_models, piper_meta = build_piper_model_options()
    piper_exe = (os.getenv("PIPER_EXECUTABLE") or "").strip()
    enabled = tts_providers_enabled()
    return {
        "providers": enabled,
        "tts_lab": {
            "TTS_PROVIDER": (os.getenv("TTS_PROVIDER") or "").strip(),
            "TTS_PROVIDER_DEFAULT": (os.getenv("TTS_PROVIDER_DEFAULT") or "").strip(),
        },
        "kokoro": {
            "available": kokoro_available,
            "voices": kokoro_ptbr_voices,
            "langs": kokoro_langs,
            "env": {
                "KOKORO_MODEL": (os.getenv("KOKORO_MODEL") or "").strip(),
                "KOKORO_VOICES": (os.getenv("KOKORO_VOICES") or "").strip(),
                "KOKORO_VOICE": (os.getenv("KOKORO_VOICE") or "").strip(),
                "KOKORO_LANG": (os.getenv("KOKORO_LANG") or "").strip(),
                "KOKORO_SPEED": (os.getenv("KOKORO_SPEED") or "").strip(),
            },
        },
        "piper": {
            "available": bool(piper_exe),
            "models": piper_models,
            "env": piper_meta.get("env", {}),
            "PIPER_VOICES_DIR": piper_meta.get("PIPER_VOICES_DIR", ""),
            "catalog_path": piper_meta.get("catalog_path", ""),
        },
        "selected": {
            "provider": tts_provider_effective(),
        },
    }


@app.get(
    "/api/lab/ui_config",
    tags=["sistema"],
    summary="Defaults da UI do laboratório (checkboxes e flags)",
)
def api_lab_ui_config() -> Dict[str, Any]:
    raw = (os.getenv("VISUAL_USE_COMFYUI_DEFAULT") or "1").strip().lower()
    visual_default = raw not in ("0", "false", "no", "off") if raw else True
    return {"visual_use_comfyui_default": visual_default}


@app.post(
    "/api/visual_agent/batch",
    tags=["visual_agent"],
    summary="Gerar clipes para várias cenas (mesmo job_path)",
)
def api_visual_batch(req: VisualBatchRequest) -> Dict[str, Any]:
    token, path = _resolve_lab_job(req.job_token)
    items = [{"scene_idx": int(a.scene_idx), "image": a.image.strip()} for a in req.assets]
    out = run_visual_batch(path, items, visual_use_comfy=req.use_comfy)
    return {**out, "job_token": token}


@app.post(
    "/api/composer_agent/preview",
    tags=["composer_agent"],
    summary="Montar final.mp4 (concat clipes + narração)",
)
def api_composer_preview(req: ComposerLabRequest) -> Dict[str, Any]:
    t = req.job_token.strip()
    if t not in _LAB_JOB_DIRS:
        raise HTTPException(status_code=404, detail="job_token desconhecido")
    path = _LAB_JOB_DIRS[t]
    out = run_composer_lab(path)
    video_url = ""
    if out.get("ok") and (out.get("video_path") or "").strip():
        video_url = f"/api/lab/job/{t}/final.mp4"
    return {**out, "job_token": t, "video_url": video_url}


@app.post(
    "/api/metadata_agent/preview",
    tags=["metadata_agent"],
    summary="Gerar título, descrição e tags (LLM) alinhado ao agente de produção",
)
def api_metadata_preview(req: MetadataLabRequest) -> Dict[str, Any]:
    state: VideoState = {
        "channel_niche": "lab",
        "job_path": "",
        "topic": (req.topic or "").strip(),
        "angle": (req.angle or "").strip(),
        "trending_data": req.trending_data if isinstance(req.trending_data, dict) else {},
        "script": req.script.strip(),
        "scenes": [],
        "raw_assets": [],
        "clips": [],
        "audio_file": "",
        "video_file": "",
        "metadata": {},
        "thumbnail": {},
        "publish_status": None,
    }
    try:
        out = metadata_agent(state)
    except Exception as e:
        logger.exception("metadata_agent falhou no lab")
        raise HTTPException(status_code=500, detail="Falha interna ao gerar metadados (ver logs do servidor).") from e
    meta = dict(out.get("metadata") or {})
    tv = meta.get("title_variants") if isinstance(meta.get("title_variants"), list) else []
    dol = meta.get("description_options") if isinstance(meta.get("description_options"), list) else []
    return {"ok": True, "metadata": meta, "title_variants": tv, "description_options": dol}


@app.post(
    "/api/publish_growth_engine/preview",
    tags=["publish_growth_engine"],
    summary="Gerar metadata + descrição (Growth Engine)",
)
def api_publish_growth_preview(req: PublishGrowthPreviewRequest) -> Dict[str, Any]:
    try:
        from workshop.publish_experiments.growth_prep_lab import run_growth_prep_from_text  # type: ignore
    except Exception as e:
        logger.exception("publish_experiments indisponível")
        raise HTTPException(status_code=500, detail="Growth Engine indisponível no servidor (ver logs).") from e

    topic = (req.topic or "").strip()
    angle = (req.angle or "").strip()
    tema = topic or angle or "vídeo"
    publico = (req.publico_alvo or "").strip() or "público geral"
    objetivo = (req.objetivo_video or "").strip() or "educar com clareza e reter atenção"
    script = req.script.strip()
    segs = req.segments if isinstance(req.segments, list) else None

    try:
        meta, growth_record = run_growth_prep_from_text(
            script=script,
            segments=segs,
            tema=tema,
            publico_alvo=publico,
            objetivo_video=objetivo,
        )
    except Exception as e:
        logger.exception("growth_engine falhou no lab")
        raise HTTPException(status_code=500, detail="Falha interna ao gerar Growth Engine (ver logs do servidor).") from e

    return {"ok": True, "metadata": meta, "growth": growth_record}


@app.post(
    "/api/thumbnail_card_agent/preview",
    tags=["thumbnail_card_agent"],
    summary="Gerar thumbnail.png (card) a partir do final.mp4",
)
def api_thumbnail_card_preview(req: ThumbnailLabRequest) -> Dict[str, Any]:
    t = req.job_token.strip()
    if t not in _LAB_JOB_DIRS:
        # permite reuso persistente quando PIPELINE_JOBS_PATH estiver ativo
        t, _ = _resolve_lab_job(t)
    path = _LAB_JOB_DIRS.get(t)
    if not path:
        raise HTTPException(status_code=404, detail="job_token desconhecido")

    video_path = os.path.join(path, "final.mp4")
    if not os.path.isfile(video_path):
        # UX do lab: evita 400 para casos comuns; a UI consegue renderizar a mensagem.
        return {"ok": False, "detail": "final.mp4 ausente — execute o compositor primeiro.", "job_token": t}

    title = (req.title or "").strip()
    meta = {"title": title} if title else {}

    logo_disk = ""
    if req.logo_data_url and str(req.logo_data_url).strip():
        logo_disk = _write_thumbnail_logo_from_data_url(path, str(req.logo_data_url).strip())
    logo_final = logo_disk or (req.logo_path or "").strip()

    thumb = {
        "mode": "auto_template",
        "template_id": (req.template_id or "logo_brand").strip() or "logo_brand",
        "fields": {
            "brand_color": (req.brand_color or "#7c5cff").strip() or "#7c5cff",
            "logo_path": logo_final,
        },
    }

    state: VideoState = {
        "channel_niche": "lab",
        "job_path": path,
        "topic": "",
        "angle": "",
        "trending_data": {},
        "script": "",
        "scenes": [],
        "raw_assets": [],
        "clips": [],
        "audio_file": os.path.join(path, "narration.wav"),
        "video_file": video_path,
        "metadata": meta,
        "thumbnail": thumb,
        "publish_status": None,
    }
    try:
        out = thumbnail_card_agent(state)
    except Exception as e:
        logger.exception("thumbnail_card_agent falhou no lab")
        raise HTTPException(status_code=500, detail="Falha interna ao gerar thumbnail (ver logs do servidor).") from e

    th = out.get("thumbnail") or {}
    out_path = str(th.get("output_path") or "").strip()
    if not out_path or not os.path.isfile(out_path):
        raise HTTPException(status_code=502, detail="falha ao gerar thumbnail")
    return {
        "ok": True,
        "job_token": t,
        "thumbnail_path": out_path,
        "thumbnail_url": f"/api/lab/job/{t}/thumbnail.png",
        "thumbnail": th,
    }


@app.post(
    "/api/youtube/upload",
    tags=["youtube"],
    summary="Upload de vídeo para o YouTube (OAuth do lab; privacy via env)",
)
def api_youtube_upload(request: Request, req: YoutubeUploadLabRequest) -> Dict[str, Any]:
    user_key = (request.cookies.get("yt_user") or "").strip()
    if not user_key:
        raise HTTPException(status_code=401, detail="OAuth YouTube não conectado (use Conectar no lab).")

    t = req.job_token.strip()
    if t not in _LAB_JOB_DIRS:
        raise HTTPException(status_code=404, detail="job_token desconhecido")
    path = _LAB_JOB_DIRS[t]
    video_path = os.path.join(path, "final.mp4")
    if not os.path.isfile(video_path):
        raise HTTPException(status_code=400, detail="final.mp4 ausente — execute o compositor primeiro.")

    creds = _load_credentials(user_key)
    if not creds:
        raise HTTPException(status_code=401, detail="Credenciais OAuth inválidas ou expiradas.")

    try:
        from google.auth.transport.requests import Request as GARequest  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.http import MediaFileUpload  # type: ignore
    except Exception as e:
        logger.exception("Dependências Google API indisponíveis")
        raise HTTPException(
            status_code=500,
            detail="Dependências Google API indisponíveis no servidor (ver logs).",
        ) from e

    try:
        creds.refresh(GARequest())
    except Exception as e:
        logger.exception("Falha ao refresh do OAuth do YouTube")
        raise HTTPException(status_code=401, detail="OAuth do YouTube expirado/ inválido. Reconecte no lab.") from e

    title = req.title.strip()[:100]
    description = (req.description or "").strip()
    tags_raw = [x.strip() for x in (req.tags_csv or "").split(",") if x.strip()][:30]
    privacy = (os.getenv("PUBLISH_PRIVACY_STATUS") or "private").strip()
    category_id = (os.getenv("YOUTUBE_CATEGORY_ID") or "28").strip()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags_raw,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }

    try:
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        ins = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = ins.next_chunk()
            if status:
                pass
        vid = str((resp or {}).get("id", "") or "").strip()
        if not vid:
            raise RuntimeError(f"Resposta sem id: {resp}")
        return {"ok": True, "video_id": vid, "publish_status": f"uploaded:{vid}", "privacy": privacy}
    except Exception as e:
        logger.exception("Falha no upload do YouTube (videos.insert)")
        raise HTTPException(status_code=500, detail="Falha interna no upload (ver logs do servidor).") from e


@app.post(
    "/api/lab/asr",
    tags=["lab_job"],
    summary="ASR (faster-whisper) sobre narration.wav do job — gera VTT/SRT/JSON",
)
def api_lab_asr(req: AsrLabRequest) -> Dict[str, Any]:
    t = req.job_token.strip()
    if t not in _LAB_JOB_DIRS:
        raise HTTPException(status_code=404, detail="job_token desconhecido")
    path = _LAB_JOB_DIRS[t]
    wav = os.path.join(path, "narration.wav")
    if not os.path.isfile(wav):
        raise HTTPException(status_code=400, detail="narration.wav ausente — execute TTS primeiro.")

    try:
        from workshop.video_compose_experiments.asr_export import (  # noqa: WPS433
            asr_result_to_json_dict,
            run_asr_to_files,
        )
    except Exception as e:
        logger.exception("Módulo ASR indisponível no servidor")
        raise HTTPException(status_code=500, detail="ASR indisponível no servidor (ver logs).") from e

    out_dir = Path(path)
    wav_p = Path(wav)
    try:
        res = run_asr_to_files(
            wav_p,
            out_dir,
            model_size=req.model_size.strip() or "small",
            language=(req.language or "pt").strip() or "pt",
            stem="narration_asr",
        )
    except Exception as e:
        logger.exception("Falha ao executar ASR")
        raise HTTPException(status_code=500, detail="Falha interna ao executar ASR (ver logs do servidor).") from e

    jpath = out_dir / "asr_words.json"
    try:
        jpath.write_text(
            json.dumps(asr_result_to_json_dict(res), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.exception("Falha ao gravar JSON do ASR")
        raise HTTPException(status_code=500, detail="Falha interna ao gravar saída do ASR (ver logs).") from e

    base = f"/api/lab/job/{t}"
    return {
        "ok": True,
        "job_token": t,
        "language": res.language,
        "duration_s": res.duration_s,
        "vtt_url": f"{base}/narration_asr.vtt",
        "srt_url": f"{base}/narration_asr.srt",
        "json_url": f"{base}/asr_words.json",
    }


@app.post(
    "/api/lab/sync_compose",
    tags=["lab_job"],
    summary="Sincronismo avançado — recompor vídeo alinhado ao áudio (timeline + ffmpeg)",
)
def api_lab_sync_compose(req: LabSyncComposeRequest) -> Dict[str, Any]:
    t = req.job_token.strip()
    if t not in _LAB_JOB_DIRS:
        raise HTTPException(status_code=404, detail="job_token desconhecido")
    path = _LAB_JOB_DIRS[t]
    try:
        from workshop.video_compose_experiments.lab_sync_compose import run_lab_sync_compose  # noqa: WPS433
    except Exception as e:
        logger.exception("Módulo lab_sync_compose indisponível")
        raise HTTPException(status_code=500, detail=f"Sincronismo avançado indisponível: {e}") from e

    out = run_lab_sync_compose(path)
    if not out.get("ok"):
        detail = str(out.get("error") or "falha desconhecida")
        raise HTTPException(status_code=400, detail=detail)

    base = f"/api/lab/job/{t}"
    return {
        "ok": True,
        "job_token": t,
        "video_url": f"{base}/final_synced.mp4",
        "timeline_url": f"{base}/aligned_timeline.json",
    }


@app.get(
    "/api/lab/job/{job_token}/narration.wav",
    tags=["lab_job"],
    summary="Descarregar narration.wav do job",
)
def lab_job_narration(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    wav = os.path.join(path, "narration.wav")
    if not os.path.isfile(wav):
        raise HTTPException(status_code=404, detail="narration.wav ausente")
    return FileResponse(wav, media_type="audio/wav", filename="narration.wav", headers={"Cache-Control": "no-store"})


@app.get(
    "/api/lab/job/{job_token}/final.mp4",
    tags=["lab_job"],
    summary="Descarregar final.mp4 do job",
)
def lab_job_final(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    mp4 = os.path.join(path, "final.mp4")
    if not os.path.isfile(mp4):
        raise HTTPException(status_code=404, detail="final.mp4 ausente")
    return FileResponse(mp4, media_type="video/mp4", filename="final.mp4", headers={"Cache-Control": "no-store"})


@app.get(
    "/api/lab/job/{job_token}/final_synced.mp4",
    tags=["lab_job"],
    summary="Descarregar final_synced.mp4 (sincronismo avançado)",
)
def lab_job_final_synced(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    mp4 = os.path.join(path, "final_synced.mp4")
    if not os.path.isfile(mp4):
        raise HTTPException(status_code=404, detail="final_synced.mp4 ausente — execute POST /api/lab/sync_compose")
    return FileResponse(mp4, media_type="video/mp4", filename="final_synced.mp4", headers={"Cache-Control": "no-store"})


@app.get(
    "/api/lab/job/{job_token}/aligned_timeline.json",
    tags=["lab_job"],
    summary="Timeline alinhada (lab sync compose)",
)
def lab_job_aligned_timeline(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    fp = os.path.join(path, "aligned_timeline.json")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="aligned_timeline.json ausente — execute POST /api/lab/sync_compose")
    return FileResponse(fp, media_type="application/json", filename="aligned_timeline.json", headers={"Cache-Control": "no-store"})


@app.get(
    "/api/lab/job/{job_token}/thumbnail.png",
    tags=["lab_job"],
    summary="Descarregar thumbnail.png do job",
)
def lab_job_thumbnail(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    p = os.path.join(path, "thumbnail.png")
    if not os.path.isfile(p):
        raise HTTPException(status_code=404, detail="thumbnail.png ausente")
    return FileResponse(p, media_type="image/png", filename="thumbnail.png", headers={"Cache-Control": "no-store"})


@app.get(
    "/api/lab/job/{job_token}/narration_asr.vtt",
    tags=["lab_job"],
    summary="Legenda WebVTT (ASR) do job",
)
def lab_job_asr_vtt(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    fp = os.path.join(path, "narration_asr.vtt")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="narration_asr.vtt ausente — execute POST /api/lab/asr")
    return FileResponse(fp, media_type="text/vtt", filename="narration_asr.vtt", headers={"Cache-Control": "no-store"})


@app.get(
    "/api/lab/job/{job_token}/narration_asr.srt",
    tags=["lab_job"],
    summary="Legenda SRT (ASR) do job",
)
def lab_job_asr_srt(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    fp = os.path.join(path, "narration_asr.srt")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="narration_asr.srt ausente — execute POST /api/lab/asr")
    return FileResponse(fp, media_type="application/x-subrip", filename="narration_asr.srt", headers={"Cache-Control": "no-store"})


@app.get(
    "/api/lab/job/{job_token}/asr_words.json",
    tags=["lab_job"],
    summary="Palavras com timestamps (ASR) do job",
)
def lab_job_asr_json(job_token: str):
    path = _LAB_JOB_DIRS.get(job_token)
    if not path:
        raise HTTPException(status_code=404, detail="job desconhecido")
    fp = os.path.join(path, "asr_words.json")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404, detail="asr_words.json ausente — execute POST /api/lab/asr")
    return FileResponse(fp, media_type="application/json", filename="asr_words.json", headers={"Cache-Control": "no-store"})


def _youtube_client_config() -> Optional[Dict[str, Any]]:
    client_id = (os.getenv("YOUTUBE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("YOUTUBE_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return None
    # "installed" funciona bem para flow local (localhost) sem secrets extras.
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _safe_mkdir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


def _channel_folder_name(channel_title: str, channel_id: str) -> str:
    """Nome de pasta por canal: título sanitizado + id (único)."""
    cid = (channel_id or "").strip()
    raw_title = (channel_title or "").strip()
    slug = _sanitize_user_key(raw_title or "channel")
    if len(slug) > 56:
        slug = slug[:56].rstrip("._-")
    if not slug:
        slug = "channel"
    return f"{slug}__{cid}" if cid else slug


def _sync_channel_credential_dirs(creds: Any, user_key: str) -> None:
    """Espelha o mesmo token OAuth numa pasta por canal (nome legível + id)."""
    try:
        from googleapiclient.discovery import build  # type: ignore

        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        r = yt.channels().list(part="snippet", mine=True).execute()
        items = r.get("items") or []
        raw_json = creds.to_json()
        for it in items:
            cid = str(it.get("id") or "").strip()
            sn = it.get("snippet") or {}
            title = str(sn.get("title") or "").strip()
            folder = _channel_folder_name(title, cid)
            base = os.path.join(CHANNELS_DIR, folder)
            _safe_mkdir(base)
            cred_path = os.path.join(base, "credentials.json")
            with open(cred_path, "w", encoding="utf-8") as f:
                f.write(raw_json)
            meta_path = os.path.join(base, "channel.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"channel_id": cid, "title": title, "account_key": user_key},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
    except Exception as e:
        logger.warning("[youtube_auth] não foi possível sincronizar pastas por canal: %s", e)


def _oauth_state_path(state: str) -> str:
    return os.path.join(OAUTH_STATES_DIR, f"{state}.json")


def _save_oauth_state(state: str, payload: Dict[str, Any]) -> None:
    try:
        _safe_mkdir(OAUTH_STATES_DIR)
        with open(_oauth_state_path(state), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


def _load_oauth_state(state: str) -> Dict[str, Any]:
    try:
        with open(_oauth_state_path(state), "r", encoding="utf-8") as f:
            data = json.load(f) or {}
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sanitize_user_key(raw_key: str) -> str:
    """
    Gera uma chave segura para nome de ficheiro.

    Importante: NÃO usar apenas a parte antes do @ (localpart), pois pode colidir entre domínios
    (ex.: flaviolopes@gmail.com vs flaviolopes@ideiasfactory.tech).
    """
    raw = (raw_key or "").strip().lower()
    out = []
    for ch in raw:
        if ch.isalnum() or ch in ("_", "-", "."):
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out).strip("._-")
    return s[:64] if s else "user"


def _token_path(user_key: str) -> str:
    return os.path.join(ACCOUNTS_DIR, _sanitize_user_key(user_key), "credentials.json")


def _save_credentials(user_key: str, creds: Any) -> None:
    try:
        _safe_mkdir(os.path.dirname(_token_path(user_key)))
        with open(_token_path(user_key), "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    except Exception:
        pass


def _load_credentials(user_key: str) -> Any:
    try:
        from google.oauth2.credentials import Credentials  # type: ignore

        path = _token_path(user_key)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return None
        data = json.loads(raw)
        return Credentials.from_authorized_user_info(data)
    except Exception:
        return None


def _get_user_email(creds: Any) -> str:
    """
    Obtém o email do utilizador autenticado para chavear o token por conta.
    Requer scope 'email' (já incluído em YOUTUBE_OAUTH_SCOPES).
    """
    try:
        import requests  # type: ignore

        r = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {getattr(creds, 'token', '')}"},
            timeout=10,
        )
        if not r.ok:
            return ""
        data = r.json() or {}
        return str(data.get("email") or "").strip()
    except Exception:
        return ""


def _get_user_sub_and_email(creds: Any) -> Dict[str, str]:
    """
    Retorna identificadores estáveis do utilizador (quando disponíveis):
    - sub: subject do Google (estável, único)
    - email: email (pode mudar, mas é útil para debug)
    """
    try:
        import requests  # type: ignore

        r = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {getattr(creds, 'token', '')}"},
            timeout=10,
        )
        if not r.ok:
            return {"sub": "", "email": ""}
        data = r.json() or {}
        return {"sub": str(data.get("id") or data.get("sub") or "").strip(), "email": str(data.get("email") or "").strip()}
    except Exception:
        return {"sub": "", "email": ""}


@app.get(
    "/api/youtube/oauth/start",
    tags=["youtube"],
    summary="Iniciar login OAuth do YouTube (abre consentimento no browser)",
)
def youtube_oauth_start(request: Request):
    """
    Inicia o OAuth no modo laboratório:
    - Abre a tela de consentimento do Google
    - Ao concluir, o callback salva o token em disco (arquivo local do BFF)
    """
    cfg = _youtube_client_config()
    if not cfg:
        return HTMLResponse(
            "<h3>Configuração ausente</h3><p>Defina <code>YOUTUBE_CLIENT_ID</code> e <code>YOUTUBE_CLIENT_SECRET</code> no .env.</p>",
            status_code=400,
        )

    try:
        from google_auth_oauthlib.flow import Flow  # type: ignore
    except Exception as e:
        logger.exception("Dependência google-auth-oauthlib indisponível")
        return HTMLResponse(
            "<h3>Dependência ausente</h3><p>Não foi possível importar google-auth-oauthlib. Verifique o servidor.</p>",
            status_code=500,
        )

    redirect_uri = (os.getenv("YOUTUBE_OAUTH_REDIRECT_URL") or "").strip()
    if not redirect_uri:
        redirect_uri = str(request.base_url).rstrip("/") + "/api/youtube/oauth/callback"

    state = secrets.token_urlsafe(20)

    flow = Flow.from_client_config(
        cfg,
        scopes=YOUTUBE_OAUTH_SCOPES,
        state=state,
    )
    flow.redirect_uri = redirect_uri

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    # PKCE: o Google exige `code_verifier` no callback. Precisamos persistir entre requests (lab sem sessão).
    _save_oauth_state(
        state,
        {"state": state, "redirect_uri": redirect_uri, "code_verifier": getattr(flow, "code_verifier", "") or ""},
    )
    return RedirectResponse(url=auth_url, status_code=302)


@app.get(
    "/api/youtube/oauth/callback",
    tags=["youtube"],
    summary="Callback OAuth do YouTube (salva token localmente)",
    include_in_schema=True,
)
def youtube_oauth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return HTMLResponse(f"<h3>OAuth cancelado/erro</h3><p>{error}</p>", status_code=400)
    if not code:
        return HTMLResponse("<h3>Callback inválido</h3><p>Parâmetro <code>code</code> ausente.</p>", status_code=400)

    saved = _load_oauth_state(state)
    expected_state = str(saved.get("state") or "")
    if expected_state and state and state != expected_state:
        return HTMLResponse("<h3>Estado inválido</h3><p>Tente conectar novamente.</p>", status_code=400)

    cfg = _youtube_client_config()
    if not cfg:
        return HTMLResponse(
            "<h3>Configuração ausente</h3><p>Defina <code>YOUTUBE_CLIENT_ID</code> e <code>YOUTUBE_CLIENT_SECRET</code> no .env.</p>",
            status_code=400,
        )

    try:
        from google_auth_oauthlib.flow import Flow  # type: ignore
    except Exception as e:
        logger.exception("Dependência google-auth-oauthlib indisponível (callback)")
        return HTMLResponse(
            "<h3>Dependência ausente</h3><p>Não foi possível importar google-auth-oauthlib. Verifique o servidor.</p>",
            status_code=500,
        )

    # Use o mesmo redirect_uri do start (ou env) para evitar mismatch.
    redirect_uri = (os.getenv("YOUTUBE_OAUTH_REDIRECT_URL") or "").strip() or str(saved.get("redirect_uri") or "").strip()
    if not redirect_uri:
        redirect_uri = str(request.base_url).rstrip("/") + "/api/youtube/oauth/callback"

    flow = Flow.from_client_config(
        cfg,
        scopes=YOUTUBE_OAUTH_SCOPES,
        state=state or None,
    )
    flow.redirect_uri = redirect_uri
    try:
        code_verifier = str(saved.get("code_verifier") or "").strip()
        if code_verifier:
            setattr(flow, "code_verifier", code_verifier)
        flow.fetch_token(code=code)
        creds = flow.credentials
        ident = _get_user_sub_and_email(creds)
        # Preferir um identificador estável e único. Fallback: email completo.
        if ident.get("sub"):
            user_key = _sanitize_user_key(f"google_{ident['sub']}")
        else:
            email = ident.get("email") or _get_user_email(creds)
            user_key = _sanitize_user_key(email or "user")
        _save_credentials(user_key, creds)
        _sync_channel_credential_dirs(creds, user_key)

        # Lembra o utilizador no browser (lab): cookie HttpOnly para resolver multiusuário sem login próprio.
        resp = RedirectResponse(url="/static/index.html#publisher", status_code=302)
        resp.set_cookie(
            "yt_user",
            user_key,
            httponly=True,
            samesite="lax",
            secure=False,  # lab local http
            max_age=60 * 60 * 24 * 30,
        )
        return resp
    except Exception as e:
        logger.exception("Falha ao salvar credenciais OAuth do YouTube")
        return HTMLResponse(
            "<h3>Falha ao salvar token</h3><p>O servidor não conseguiu concluir o OAuth. Verifique logs.</p>",
            status_code=500,
        )


@app.get(
    "/api/youtube/channels",
    tags=["youtube"],
    summary="Listar canais do usuário autenticado",
)
def youtube_list_channels(request: Request, user: str = "") -> Dict[str, Any]:
    user_key = (user or request.cookies.get("yt_user") or "").strip()
    if not user_key:
        return {"status": "not_connected", "channels": []}

    creds = _load_credentials(user_key)
    if not creds:
        return {"status": "not_connected", "channels": []}

    try:
        from googleapiclient.discovery import build  # type: ignore
    except Exception as e:
        logger.exception("google-api-python-client indisponível (channels)")
        return {"status": "error", "detail": "Dependência google-api-python-client indisponível no servidor.", "channels": []}

    try:
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        r = yt.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()
        items = r.get("items", []) or []
        channels = []
        for it in items:
            sn = it.get("snippet") or {}
            channels.append(
                {
                    "id": it.get("id"),
                    "title": sn.get("title") or "",
                    "custom_url": sn.get("customUrl") or "",
                    "published_at": sn.get("publishedAt") or "",
                }
            )
        return {"status": "ok", "channels": channels}
    except Exception as e:
        logger.exception("Falha ao listar canais do YouTube")
        return {"status": "error", "detail": "Falha interna ao listar canais (ver logs do servidor).", "channels": []}
