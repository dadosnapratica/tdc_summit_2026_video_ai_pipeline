"""
Modelos Pydantic compartilhados para OpenAPI (workshop.bff.lab_server).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


DurationTier = Literal["short", "medium", "long", "too_long", "custom"]


class AnglesResponse(BaseModel):
    tema: str = Field(description="Tema repetido ou normalizado.")
    angles: List[str] = Field(description="Lista de ângulos narrativos sugeridos.")


class GenerateRequest(BaseModel):
    tema: str = Field(description="Tema central do vídeo (obrigatório; sem padrão no servidor).")
    angulo: str = Field(default="", description="Ângulo narrativo (pode ser vazio).")
    use_ollama: Optional[bool] = Field(default=None, description="Se definido, sobrescreve USE_OLLAMA no processo (1/0).")
    youtube_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadados opcionais vindos do Research (YouTube) para enriquecer o roteiro.",
    )
    duration_tier: DurationTier = Field(
        default="medium",
        description=(
            "Perfil de duração da narração: short (≤~90s), medium (~5min), long (10–15min), "
            "too_long (20–30min), custom (use target_narration_minutes)."
        ),
    )
    target_narration_minutes: Optional[float] = Field(
        default=None,
        ge=1,
        le=60,
        description="Obrigatório se duration_tier=custom: duração alvo estimada da narração em minutos (1–60).",
    )

    @field_validator("tema")
    @classmethod
    def _tema_required_stripped(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise TypeError("tema deve ser string")
        s = v.strip()
        if not s:
            raise ValueError("tema é obrigatório")
        return s

    @model_validator(mode="after")
    def _custom_requires_target_minutes(self) -> "GenerateRequest":
        if self.duration_tier == "custom" and self.target_narration_minutes is None:
            raise ValueError("Quando duration_tier é 'custom', defina target_narration_minutes (1–60).")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tema": "história da música popular brasileira",
                    "angulo": "Bossa nova e sua recepção no exterior",
                    "use_ollama": True,
                    "duration_tier": "medium",
                },
                {
                    "tema": "economia comportamental",
                    "angulo": "guia rápido para iniciantes",
                    "duration_tier": "custom",
                    "target_narration_minutes": 7,
                },
            ]
        }
    }


class ResearchRequest(BaseModel):
    keyword: str = Field(description="Palavra-chave ou tema para Trends + YouTube.")
    region: str = Field(default="BR", description="Código de região (ex.: BR, US).")
    category_id: str = Field(default="28", description="ID de categoria YouTube (28 = ciência/tecnologia).")
    youtube_n: int = Field(default=10, ge=1, le=50, description="Quantidade de vídeos YouTube.")
    trends_days: int = Field(default=7, ge=1, le=90, description="Janela em dias para Google Trends.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "keyword": "astronomia",
                    "region": "BR",
                    "category_id": "28",
                    "youtube_n": 10,
                    "trends_days": 7,
                }
            ]
        }
    }


class ImageSearchRequest(BaseModel):
    scene: str = Field(description="Descrição da cena / prompt de busca.")
    style: str = Field(default="", description="Guia de estilo opcional (ou IMAGE_RESEARCH_STYLE_GUIDE).")
    prefer: Optional[
        Literal["video_first", "image_first", "all", "video", "image"]
    ] = Field(
        default=None,
        description=(
            "Preferência de mídia: "
            "video_first, image_first, all (imagem ou vídeo; ranker LLM/heurística sem viés de tipo), "
            "video/image (só esse tipo). "
            "Se omitido, usa ASSET_RESEARCH_PREFERENCE no servidor."
        ),
    )
    per_source: int = Field(default=5, ge=1, le=50, description="Máximo de candidatos por fonte de imagem.")

    @field_validator("prefer", mode="before")
    @classmethod
    def _normalize_prefer(cls, v: Union[str, None]) -> Union[str, None]:
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s:
            return None
        if s == "any":
            return "all"
        return s

    model_config = {
        "json_schema_extra": {
            "examples": [{"scene": "nebulosa em tons de roxo", "style": "cinematográfico", "per_source": 5}]
        }
    }


class VisualLabRequest(BaseModel):
    image: str = Field(
        description="URL http(s) de uma imagem ou caminho local acessível pelo processo do BFF.",
    )
    scene_idx: int = Field(default=0, ge=0, le=999, description="Índice da cena (alinhado a scene_idx do asset).")
    use_comfy: Optional[bool] = Field(
        default=None,
        description="None → usa VISUAL_USE_COMFYUI_DEFAULT; True → tenta ComfyUI; False → só ffmpeg.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "image": "https://images.pexels.com/photos/2150/sky-space-dark-galaxy.jpg",
                    "scene_idx": 0,
                    "use_comfy": True,
                }
            ]
        }
    }


class VisualBatchAsset(BaseModel):
    scene_idx: int = Field(ge=0, le=999)
    image: str = Field(min_length=1, description="URL ou path local da imagem da cena.")


class VisualBatchRequest(BaseModel):
    job_token: Optional[str] = Field(
        default=None,
        description="Sessão partilhada com TTS/compositor; omitido cria um job novo.",
    )
    assets: List[VisualBatchAsset] = Field(
        min_length=1,
        description="Uma entrada por cena com imagem selecionada (Image Research).",
    )
    use_comfy: Optional[bool] = Field(
        default=None,
        description="None → usa VISUAL_USE_COMFYUI_DEFAULT; True → tenta ComfyUI; False → só ffmpeg.",
    )


class TtsLabRequest(BaseModel):
    script: str = Field(min_length=1, description="Texto completo da narração (PT-BR), ex.: textos do roteiro unidos.")
    job_token: Optional[str] = Field(default=None, description="Sessão partilhada; omitido cria um job novo.")
    provider: Optional[Literal["kokoro", "piper"]] = Field(
        default=None,
        description=(
            "Motor TTS para este pedido; tem de estar em TTS_PROVIDER (CSV). "
            "Se omitido, usa TTS_PROVIDER_DEFAULT (se válido) ou o primeiro da lista habilitada."
        ),
    )
    kokoro_voice: Optional[str] = Field(default=None, description="Se definido, sobrescreve KOKORO_VOICE para este request.")
    kokoro_lang: Optional[str] = Field(default=None, description="Se definido, sobrescreve KOKORO_LANG para este request (ex.: pt-br).")
    kokoro_speed: Optional[float] = Field(default=None, ge=0.5, le=2.0, description="Sobrescreve KOKORO_SPEED (0.5–2.0).")
    piper_model: Optional[str] = Field(
        default=None,
        description="Com provider=piper: caminho absoluto ao .onnx ou id (ex. pt_BR-faber-medium) em PIPER_VOICES_DIR.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"script": "Olá. Neste vídeo falamos de astronomia.", "job_token": ""},
                {"script": "Olá. Teste com Kokoro.", "provider": "kokoro", "kokoro_voice": "pf_dora", "kokoro_lang": "pt-br"},
                {"script": "Teste Piper.", "provider": "piper", "piper_model": "pt_BR-faber-medium"},
            ]
        }
    }


class ComposerLabRequest(BaseModel):
    job_token: str = Field(min_length=1, description="Token devolvido pelos passos TTS/visual nesta sessão.")


class MetadataLabRequest(BaseModel):
    topic: str = Field(default="", description="Tema (VideoState.topic).")
    angle: str = Field(default="", description="Ângulo narrativo (VideoState.angle).")
    script: str = Field(min_length=1, description="Roteiro completo para SEO/metadata.")
    trending_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Opcional: resumo de research/trends (VideoState.trending_data).",
    )


class ThumbnailLabRequest(BaseModel):
    job_token: str = Field(min_length=1, description="Job com final.mp4 (composer) e metadados.")
    template_id: str = Field(default="logo_brand", description="Template da thumbnail (ex.: logo_brand).")
    brand_color: str = Field(default="#7c5cff", description="Cor de marca em hex (ex.: #7c5cff).")
    title: str = Field(default="", description="Título/overlay opcional (fallback para metadata.title).")
    logo_path: str = Field(default="", description="Path opcional do logo no servidor (se existir).")
    logo_data_url: Optional[str] = Field(
        default=None,
        description="Opcional: data:image/png;base64,... (ou jpeg/webp) — gravado no job e usado como logo.",
    )


class PublishGrowthPreviewRequest(BaseModel):
    topic: str = Field(default="", description="Tema (title/SEO).")
    angle: str = Field(default="", description="Ângulo narrativo (contexto).")
    publico_alvo: str = Field(default="", description="Público-alvo (persona).")
    objetivo_video: str = Field(default="", description="Objetivo do vídeo (ex.: educar, converter, reter).")
    script: str = Field(min_length=1, description="Roteiro completo para growth engine.")
    trending_data: Optional[Dict[str, Any]] = Field(default=None, description="Sinais opcionais de research/trends.")
    segments: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Opcional: segmentos da timeline (start_s, caption_text, script_part_id...).",
    )


class YoutubeUploadLabRequest(BaseModel):
    job_token: str = Field(min_length=1, description="Job com final.mp4 e metadados.")
    title: str = Field(min_length=1, max_length=100, description="Título do vídeo (snippet).")
    description: str = Field(default="", description="Descrição (snippet).")
    tags_csv: str = Field(default="", description="Tags separadas por vírgula.")
    channel_id: str = Field(default="", description="ID do canal YouTube (deve coincidir com um canal OAuth).")


class AsrLabRequest(BaseModel):
    job_token: str = Field(min_length=1, description="Job com narration.wav.")
    model_size: str = Field(default="small", description="Tamanho do modelo faster-whisper (tiny, base, small, …).")
    language: str = Field(default="pt", description="Idioma para transcrição.")


class LabSyncComposeRequest(BaseModel):
    job_token: str = Field(min_length=1, description="Job com script_lab, ASR, clipes e narration.wav.")
    timeline_mode: str = Field(
        default="auto",
        description="Reservado; atualmente só ``auto`` (segmentação dinâmica alinhada ao ASR).",
    )


class LivenessResponse(BaseModel):
    status: Literal["ok"] = Field(default="ok", description="Processo vivo.")


class HealthResponse(BaseModel):
    service: str = Field(description="Nome do serviço.")
    status: Literal["ok", "degraded"] = Field(
        description="ok = todas as sondagens críticas passaram; degraded = alguma dependência falhou."
    )
    checks: Dict[str, Any] = Field(description="Resultado por recurso (ollama, pytrends, youtube_api, image_search_keys).")
    errors: List[str] = Field(description="Chaves de checks com status error.")
