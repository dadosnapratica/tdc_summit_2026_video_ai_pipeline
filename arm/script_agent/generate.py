from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

# Sem tema/ângulo “padrão” no servidor: o operador define na UI ou no request.
# Fallbacks abaixo são apenas estrutura neutra (placeholders), nunca um nicho fixo.

DEFAULT_STYLE_GUIDE = (
    "Style: cinematic documentary, realistic, high detail, 16:9, 1080p, "
    "no text, no logos, no watermarks."
)
DEFAULT_TOTAL_SECONDS = 8 * 60  # 8 min (experimento)
DEFAULT_WPM = 155  # palavras por minuto (narração PT-BR aproximada)
DEFAULT_DURATION_TIER = "medium"

# Perfis de duração da narração (alvo para prompt LLM + metadados; pipeline visual/TTS pode variar).
_DURATION_TIERS = frozenset({"short", "medium", "long", "too_long", "custom"})


def resolve_duration_config(
    tier: str,
    target_narration_seconds: Optional[int],
    *,
    wpm: int = DEFAULT_WPM,
) -> Dict[str, Any]:
    """
    Deriva faixas de tempo, contagem de cenas sugerida e limites de palavras a partir do tier.
    `custom` exige `target_narration_seconds` (60–3600). (No laboratório web, o usuário informa minutos.)
    """
    raw = (tier or DEFAULT_DURATION_TIER).strip().lower()
    if raw not in _DURATION_TIERS:
        raw = DEFAULT_DURATION_TIER
    wpm_i = max(80, int(wpm))

    if raw == "custom":
        if target_narration_seconds is None:
            raise ValueError("target_narration_seconds é obrigatório quando duration_tier=custom")
        ts = int(target_narration_seconds)
        ts = max(60, min(3600, ts))
        lo = max(60, int(ts * 0.9))
        hi = min(3600, int(ts * 1.1))
        total_s = ts
        n_mid = max(3, min(40, int(round(ts / 55.0))))
        scene_lo = max(3, n_mid - 4)
        scene_hi = min(40, n_mid + 6)
        label = (
            f"aproximadamente {ts} segundos de narração (~{ts // 60} min {ts % 60}s); "
            f"total falado entre ~{lo} e ~{hi} segundos em ritmo natural"
        )
    elif raw == "short":
        lo, hi, total_s, scene_lo, scene_hi = 60, 90, 90, 3, 5
        label = "até 1 minuto e 30 segundos de narração"
    elif raw == "medium":
        lo, hi, total_s, scene_lo, scene_hi = 270, 330, 300, 6, 10
        label = "cerca de 5 minutos de narração (aprox. 270–330 segundos)"
    elif raw == "long":
        lo, hi, total_s, scene_lo, scene_hi = 600, 900, 780, 12, 18
        label = "entre 10 e 15 minutos de narração (aprox. 600–900 segundos)"
    else:  # too_long
        lo, hi, total_s, scene_lo, scene_hi = 1200, 1800, 1500, 20, 32
        label = "entre 20 e 30 minutos de narração (aprox. 1200–1800 segundos)"

    words_lo = max(1, int((lo / 60.0) * wpm_i))
    words_hi = max(words_lo + 1, int((hi / 60.0) * wpm_i))
    return {
        "tier": raw,
        "narration_lo_s": lo,
        "narration_hi_s": hi,
        "total_seconds": total_s,
        "scene_lo": scene_lo,
        "scene_hi": scene_hi,
        "duration_label": label,
        "words_lo": words_lo,
        "words_hi": words_hi,
        "wpm": wpm_i,
    }


def _duration_response_block(dcfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tier": dcfg["tier"],
        "narration_target_s_min": dcfg["narration_lo_s"],
        "narration_target_s_max": dcfg["narration_hi_s"],
        "total_seconds_plan": dcfg["total_seconds"],
        "scene_count_min": dcfg["scene_lo"],
        "scene_count_max": dcfg["scene_hi"],
        "words_approx_min": dcfg["words_lo"],
        "words_approx_max": dcfg["words_hi"],
        "wpm_reference": dcfg["wpm"],
    }


def _neutral_angle_suggestions() -> List[str]:
    """Sugestões genéricas quando não há tema (ex.: GET /api/angles sem query)."""
    return [
        "Introdução ao tema e por que importa agora",
        "Um conceito central com exemplo concreto",
        "Erros comuns e como interpretar melhor as informações",
        "História ou caso que ilustra o assunto",
        "O que mudou recentemente e o que ainda está em aberto",
    ]


def _heuristic_angles(tema: str) -> List[str]:
    """Deriva só a partir do texto do tema — sem ramos por nicho hardcoded."""
    t = (tema or "").strip()
    if not t:
        return _neutral_angle_suggestions()
    return [
        f"Guia para iniciantes em “{tema}” (o essencial em poucos minutos)",
        f"Três pontos polêmicos ou mal compreendidos sobre “{tema}”",
        f"Erros comuns ao falar de “{tema}” (e como evitar)",
        f"Um exemplo real que ilustra “{tema}” melhor que teoria",
        f"“{tema}”: o que mudou recentemente e por que isso importa",
    ]



def _short_angle_for_scene(angulo: str, *, max_len: int = 120) -> str:
    """Primeiro segmento útil do ângulo (listas com 🔹/•) para prompts de busca."""
    raw = (angulo or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in re.split(r"[\U00002700-\U000027BF\U0001F300-\U0001FAFF•]+", raw) if p.strip()]
    s = parts[0] if parts else raw
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[: max_len - 3].rsplit(" ", 1)[0] + "..."
    return s


def _template_scenes(tema: str, angulo: str) -> List[str]:
    """
    Prompts visuais (EN) só ancorados no tema/ângulo enviados — sem presets por nicho no código.
    """
    ang_short = _short_angle_for_scene(angulo)
    return [
        f"Scene 1: cinematic establishing shot representing '{tema}', documentary realism. {DEFAULT_STYLE_GUIDE}",
        f"Scene 2: detail shot illustrating '{ang_short or angulo}', consistent with '{tema}'. {DEFAULT_STYLE_GUIDE}",
        f"Scene 3: real-world context for '{tema}', showing '{ang_short or angulo}', documentary photo. {DEFAULT_STYLE_GUIDE}",
        f"Scene 4: conceptual visualization (no text on screen) for '{tema}' and '{ang_short or angulo}'. {DEFAULT_STYLE_GUIDE}",
        f"Scene 5: human activity or hands-on moment tied to '{tema}', environment visible. {DEFAULT_STYLE_GUIDE}",
        f"Scene 6: dramatic moment still tied to '{tema}', '{ang_short or angulo}', cinematic lighting. {DEFAULT_STYLE_GUIDE}",
        f"Scene 7: calmer reflective frame that still shows subject matter of '{tema}'. {DEFAULT_STYLE_GUIDE}",
        f"Scene 8: closing wide shot reinforcing '{tema}', inspiring documentary tone. {DEFAULT_STYLE_GUIDE}",
    ]


def _fmt_timecode(seconds: int) -> str:
    m = max(0, seconds) // 60
    s = max(0, seconds) % 60
    return f"{m:02d}:{s:02d}"


def _template_scene_plan(scenes: List[str], *, total_seconds: int = DEFAULT_TOTAL_SECONDS) -> List[Dict[str, Any]]:
    """
    Cria um plano de encaixe das cenas no timing do roteiro.
    Heurística simples alinhada à estrutura:
      - Abertura: 0:00–0:20 (1 cena)
      - Contexto: 0:20–1:20 (1-2 cenas)
      - Desenvolvimento: ~1:20–6:30 (3-5 cenas)
      - Virada: ~6:30–7:20 (1 cena)
      - Encerramento: resto (1 cena)
    """
    n = len(scenes)
    if n <= 0:
        return []

    # Marcadores base (em segundos), escaláveis ao total.
    base = {
        "abertura_end": 20,
        "contexto_end": 80,
        "desenv_end": 390,
        "virada_end": 440,
        "fim": 470,
    }
    scale = total_seconds / max(1, base["fim"])
    abertura_end = int(base["abertura_end"] * scale)
    contexto_end = int(base["contexto_end"] * scale)
    desenv_end = int(base["desenv_end"] * scale)
    virada_end = int(base["virada_end"] * scale)
    fim = int(base["fim"] * scale)

    # Distribuição de cenas por bloco dependendo de n.
    # Padrão para 8 cenas: 1/1/4/1/1
    if n <= 6:
        alloc = (1, 1, max(2, n - 3), 1, max(0, n - (1 + 1 + max(2, n - 3) + 1)))
    elif n == 7:
        alloc = (1, 1, 3, 1, 1)
    elif n == 8:
        alloc = (1, 1, 4, 1, 1)
    else:
        # 9-10+: coloca 2 no contexto e mais no desenvolvimento
        alloc = (1, 2, n - 1 - 2 - 1 - 1, 1, 1)

    a_open, a_ctx, a_dev, a_twist, a_close = alloc
    blocks = [
        ("Abertura", 0, abertura_end, a_open),
        ("Contexto", abertura_end, contexto_end, a_ctx),
        ("Desenvolvimento", contexto_end, desenv_end, a_dev),
        ("Virada", desenv_end, virada_end, a_twist),
        ("Encerramento", virada_end, fim, a_close),
    ]

    plan: List[Dict[str, Any]] = []
    idx = 0
    for section, start_s, end_s, count in blocks:
        if count <= 0:
            continue
        remaining = n - idx
        count = min(count, remaining)
        if count <= 0:
            continue

        span = max(1, end_s - start_s)
        step = span / count
        for j in range(count):
            s0 = int(start_s + j * step)
            s1 = int(start_s + (j + 1) * step) if j < count - 1 else int(end_s)
            plan.append(
                {
                    "scene_idx": idx,
                    "section": section,
                    "start": _fmt_timecode(s0),
                    "end": _fmt_timecode(s1),
                    "prompt": scenes[idx],
                }
            )
            idx += 1

    # Se sobrou alguma cena (por arredondamento), joga no Encerramento.
    while idx < n:
        plan.append(
            {
                "scene_idx": idx,
                "section": "Encerramento",
                "start": _fmt_timecode(fim),
                "end": _fmt_timecode(total_seconds),
                "prompt": scenes[idx],
            }
        )
        idx += 1

    return plan


def _template_outline(tema: str, angulo: str) -> List[Dict[str, str]]:
    """
    Roteiro base (outline) com IDs estáveis para HITL.
    """
    return [
        {"id": "title", "title": f"{tema.title()} — {angulo}"},
        {"id": "hook", "title": "Abertura (gancho + promessa)"},
        {"id": "context", "title": "Contexto (definição + por que importa)"},
        {"id": "p1", "title": "Ponto 1 (explicação + analogia)"},
        {"id": "p2", "title": "Ponto 2 (exemplo concreto)"},
        {"id": "p3", "title": "Ponto 3 (mito/objeção + correção)"},
        {"id": "twist", "title": "Virada (insight principal)"},
        {"id": "close", "title": "Encerramento (recap + pergunta/CTA)"},
    ]


def _template_outline_for_duration(tema: str, angulo: str, *, dcfg: Dict[str, Any]) -> List[Dict[str, str]]:
    """Outline do modo template ajustado pela duração alvo."""
    tier = str(dcfg.get("tier") or "").strip().lower()
    total_seconds = int(dcfg.get("total_seconds") or DEFAULT_TOTAL_SECONDS)

    if tier == "short":
        return [
            {"id": "title", "title": f"{tema.title()} — {angulo}"},
            {"id": "hook", "title": "Abertura (gancho + promessa)"},
            {"id": "p1", "title": "Ponto central (explicação simples + analogia)"},
            {"id": "close", "title": "Encerramento (recap + pergunta/CTA)"},
        ]

    # médio = estrutura padrão
    if tier == "medium":
        return _template_outline(tema, angulo)

    # long/too_long/custom: mais pontos no miolo
    # Heurística: ~1 ponto a cada ~90s (capado).
    n_points = max(4, min(16, int(round(total_seconds / 90.0))))
    points: List[Dict[str, str]] = []
    for i in range(1, n_points + 1):
        if i == 1:
            points.append({"id": "p1", "title": "Ponto 1 (explicação + analogia)"})
        elif i == 2:
            points.append({"id": "p2", "title": "Ponto 2 (exemplo concreto)"})
        elif i == 3:
            points.append({"id": "p3", "title": "Ponto 3 (mito/objeção + correção)"})
        else:
            points.append({"id": f"p{i}", "title": f"Ponto {i} (detalhe + implicação + exemplo)"} )

    return [
        {"id": "title", "title": f"{tema.title()} — {angulo}"},
        {"id": "hook", "title": "Abertura (gancho + promessa)"},
        {"id": "context", "title": "Contexto (definição + por que importa)"},
        *points,
        {"id": "twist", "title": "Virada (insight principal)"},
        {"id": "close", "title": "Encerramento (recap + pergunta/CTA)"},
    ]


def _outline_to_text(outline: List[Dict[str, str]]) -> str:
    lines = ["ROTEIRO BASE (outline)"]
    for i, item in enumerate(outline, start=1):
        lines.append(f"{i:02d}. [{item['id']}] {item['title']}")
    return "\n".join(lines)


def _template_part_texts(
    tema: str,
    angulo: str,
    outline: List[Dict[str, str]],
    *,
    research_block: str = "",
    dcfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Texto detalhado por parte, referenciando os IDs do outline.
    """
    title = next((o["title"] for o in outline if o.get("id") == "title"), f"{tema.title()} — {angulo}")
    parts: List[Dict[str, str]] = []

    words_target_total: Optional[int] = None
    if dcfg and isinstance(dcfg, dict):
        try:
            words_target_total = int(round((int(dcfg["words_lo"]) + int(dcfg["words_hi"])) / 2))
        except Exception:
            words_target_total = None

    point_ids = [
        str(o.get("id"))
        for o in outline
        if isinstance(o, dict) and re.fullmatch(r"p\d+", str(o.get("id", "")))
    ]
    n_points = max(1, len(point_ids)) if words_target_total else 0

    def target_for_part(pid: str) -> Optional[int]:
        if not words_target_total:
            return None
        if pid == "hook":
            return max(60, int(words_target_total * 0.12))
        if pid == "context":
            return max(90, int(words_target_total * 0.16))
        if pid == "twist":
            return max(70, int(words_target_total * 0.10))
        if pid == "close":
            return max(70, int(words_target_total * 0.12))
        if re.fullmatch(r"p\d+", pid or ""):
            rest = max(240, words_target_total - int(words_target_total * 0.50))
            return max(110, int(rest / max(1, n_points)))
        return None
    for o in outline:
        pid = str(o.get("id", ""))
        if pid == "title":
            parts.append({"id": "title", "text": f"Título: {title}"})
        elif pid == "hook":
            parts.append(
                {
                    "id": "hook",
                    "text": (
                        f"Quando a gente fala de {tema}, o que muda na leitura do assunto se olharmos para {angulo.lower()}?\n"
                        "Hoje eu vou focar no essencial sem enrolação — para você sair com a ideia central clara "
                        "e saber por que isso importa."
                    ),
                }
            )
        elif pid == "context":
            base = (
                f"Antes, contexto rápido. O tema “{tema}” vale ser delimitado com calma: do que estamos falando, "
                "o que é dado e o que é interpretação.\n"
                "E por que isso importa agora? Porque há muita informação solta — e misturar achismo com evidência "
                "é fácil quando o assunto viraliza."
            )
            parts.append({"id": "context", "text": (base + ("\n\n" + research_block if research_block else ""))})
        elif pid == "p1":
            parts.append(
                {
                    "id": "p1",
                    "text": (
                        "Ponto 1: uma explicação simples.\n"
                        "Pensa no tema como um mapa incompleto: costumamos ver só alguns pontos e precisamos ligá-los "
                        "sem confundir suposição com evidência.\n"
                        "Analogia: como reconstruir uma conversa ouvindo só parte das frases — você infere contexto "
                        "e confirma depois onde for possível."
                    ),
                }
            )
        elif pid == "p2":
            base = (
                "Ponto 2: um exemplo concreto.\n"
                "Aqui você traz um caso real ligado ao ângulo: um registro, um dado publicado, um documento "
                "ou um evento que mudou a interpretação.\n"
                "O objetivo é dar ‘cara’ ao conceito: o que aconteceu, por que importou, e o que dá para concluir "
                "com segurança."
            )
            parts.append({"id": "p2", "text": (base + ("\n\n" + research_block if research_block else ""))})
        elif pid == "p3":
            parts.append(
                {
                    "id": "p3",
                    "text": (
                        "Ponto 3: mito comum e correção.\n"
                        "Pegue uma frase típica que as pessoas repetem e explique onde ela erra.\n"
                        "Mostre a versão correta com linguagem simples e um detalhe memorável."
                    ),
                }
            )
        elif pid == "twist":
            parts.append(
                {
                    "id": "twist",
                    "text": (
                        "Virada: aqui vai o insight que amarra tudo.\n"
                        "Quando você entende esse ponto, percebe que dá para separar o que é evidência "
                        "do que é só narrativa forte.\n"
                        "E isso muda as perguntas que você faz daqui pra frente."
                    ),
                }
            )
        elif pid == "close":
            parts.append(
                {
                    "id": "close",
                    "text": (
                        "Recap rápido: (1) explicamos a base, (2) vimos um exemplo real, (3) derrubamos um mito.\n"
                        "Agora eu quero saber: qual parte desse tema mais te intriga — e qual mito você mais escuta por aí?"
                    ),
                }
            )
        elif re.fullmatch(r"p\d+", pid or ""):
            # Pontos adicionais (p4+): mantém formato consistente e expande para vídeos longos.
            n = int(pid[1:]) if pid[1:].isdigit() else 0
            parts.append(
                {
                    "id": pid,
                    "text": (
                        f"Ponto {n}: detalhe e implicação.\n"
                        "Explique um aspecto complementar do tema com linguagem simples.\n"
                        "Inclua um exemplo concreto e feche com uma frase que conecte ao próximo ponto."
                    ),
                }
            )
        else:
            parts.append({"id": pid or "part", "text": str(o.get("title", "")).strip()})

        if parts and parts[-1].get("id") != "title":
            tgt = target_for_part(str(parts[-1]["id"]))
            if tgt:
                parts[-1]["text"] = _pad_text_to_words(
                    str(parts[-1]["text"]),
                    target_words=tgt,
                    tema=tema,
                    angulo=angulo,
                    pid=str(parts[-1]["id"]),
                )
    return parts


def _count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or "", flags=re.UNICODE))


def _pad_text_to_words(text: str, *, target_words: int, tema: str, angulo: str, pid: str) -> str:
    """
    Expande texto do modo template até uma contagem aproximada de palavras.
    Objetivo: aproximar a duração por profile sem depender de LLM.
    """
    t = (text or "").strip()
    target = max(30, int(target_words))
    if _count_words(t) >= target:
        return t

    extra_blocks: List[str] = []
    if pid == "hook":
        extra_blocks.append(
            "Fica comigo até o final porque eu vou te dar um jeito simples de organizar isso na cabeça — "
            "sem precisar decorar termos difíceis."
        )
    elif pid == "context":
        extra_blocks.append(
            f"Quando falamos de {tema}, a chave é separar observação, interpretação e mito. "
            "Muita confusão nasce quando a gente tenta explicar tudo com uma única frase."
        )
    elif re.fullmatch(r"p\d+", pid or ""):
        extra_blocks.append(
            "Para fixar, pensa em três perguntas: o que foi observado, qual a hipótese mais provável, "
            "e o que ainda é incerteza. Isso te ajuda a não cair em exageros."
        )
        extra_blocks.append(
            "Exemplo rápido: pegue uma notícia recente, procure o dado original (imagem, medição, artigo), "
            "e compare com o título. Quase sempre o título simplifica demais."
        )
        extra_blocks.append(
            "Se você quiser ir um pouco além, procure uma fonte primária confiável sobre o tema e "
            "anote duas frases: o que parece bem apoiado e o que ainda está em debate ou incerto."
        )
    elif pid == "twist":
        extra_blocks.append(
            f"A virada aqui é perceber que {angulo.lower()} fica muito mais claro quando você olha para evidências "
            "e não para opiniões soltas."
        )
    elif pid == "close":
        extra_blocks.append(
            "Se você gostou desse formato, comenta qual ponto você quer ver em mais detalhe — eu posso transformar isso "
            "em uma série curta com exemplos reais."
        )

    out = t
    i = 0
    while _count_words(out) < target and i < 16:
        if not extra_blocks:
            break
        out += "\n\n" + extra_blocks[i % len(extra_blocks)]
        i += 1
    return out.strip()


def _estimate_seconds_from_text(text: str, *, wpm: int = DEFAULT_WPM) -> int:
    wpm = max(80, int(wpm))
    words = _count_words(text)
    return int(round((words / wpm) * 60))


def _allocate_timecodes(
    part_texts: List[Dict[str, str]],
    *,
    wpm: int = DEFAULT_WPM,
    pad_seconds: int = 20,
) -> List[Dict[str, Any]]:
    durations: List[int] = []
    for p in part_texts:
        if p.get("id") == "title":
            durations.append(0)
        else:
            durations.append(max(8, _estimate_seconds_from_text(p.get("text", ""), wpm=wpm)))

    total = sum(durations) + pad_seconds
    cursor = 0
    out: List[Dict[str, Any]] = []
    for p, dur in zip(part_texts, durations, strict=False):
        pid = str(p.get("id", ""))
        if pid == "title":
            out.append({"id": pid, "start_s": 0, "end_s": 0, "duration_s": 0})
            continue
        start_s = cursor
        end_s = cursor + dur
        out.append({"id": pid, "start_s": start_s, "end_s": end_s, "duration_s": dur})
        cursor = end_s

    # adiciona pad no último bloco não-title
    for i in range(len(out) - 1, -1, -1):
        if out[i].get("id") != "title":
            out[i]["end_s"] = int(out[i]["end_s"]) + pad_seconds
            out[i]["duration_s"] = int(out[i]["duration_s"]) + pad_seconds
            break

    out.append({"id": "_total", "total_s": total})
    return out


def _scenes_from_parts(
    tema: str,
    angulo: str,
    part_texts: List[Dict[str, str]],
    time_plan: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    prompts = _template_scenes(tema, angulo)
    times = {t["id"]: (int(t.get("start_s", 0)), int(t.get("end_s", 0))) for t in time_plan if "start_s" in t}

    part_ids = [p.get("id") for p in part_texts if p.get("id") not in ("title",)]
    # Mantém ordem: hook/context → p1..pN → twist/close
    points = [str(pid) for pid in part_ids if isinstance(pid, str) and re.fullmatch(r"p\d+", pid)]
    def _pnum(x: str) -> int:
        try:
            return int(x[1:])
        except Exception:
            return 10_000
    points = sorted(points, key=_pnum)
    buckets: List[str] = []
    for k in ("hook", "context"):
        if k in part_ids:
            buckets.append(k)
    buckets.extend([p for p in points if p not in buckets])
    for k in ("twist", "close"):
        if k in part_ids:
            buckets.append(k)
    if not buckets:
        buckets = [str(pid) for pid in part_ids if pid]

    if len(prompts) < len(buckets):
        while len(prompts) < len(buckets):
            prompts.append(
                f"Scene {len(prompts)+1}: documentary B-roll representing '{tema}' and '{angulo}', realistic. {DEFAULT_STYLE_GUIDE}"
            )

    prompt_idx = 0
    bucket_to_prompts: Dict[str, List[str]] = {b: [] for b in buckets}
    for b in buckets:
        bucket_to_prompts[b].append(prompts[prompt_idx])
        prompt_idx += 1

    dev_targets = [b for b in ("p1", "p2", "p3") if b in bucket_to_prompts] or buckets
    dev_i = 0
    while prompt_idx < len(prompts):
        pr = prompts[prompt_idx]
        pr_l = pr.lower()
        # Heurística: prompts de "final" devem ir para fechamento, não para desenvolvimento.
        if ("sunrise" in pr_l or "ending" in pr_l or "closing" in pr_l) and "close" in bucket_to_prompts:
            bucket_to_prompts["close"].append(pr)
        else:
            bucket_to_prompts[dev_targets[dev_i % len(dev_targets)]].append(pr)
        prompt_idx += 1
        dev_i += 1

    scenes: List[Dict[str, Any]] = []
    scene_idx = 0
    for part_id in buckets:
        start_s, end_s = times.get(part_id, (0, 0))
        part_prompts = bucket_to_prompts.get(part_id, [])
        if not part_prompts:
            continue
        span = max(1, end_s - start_s) if end_s > start_s else max(8, len(part_prompts) * 6)
        step = span / len(part_prompts)
        for j, pr in enumerate(part_prompts):
            s0 = int(start_s + j * step)
            s1 = int(start_s + (j + 1) * step) if j < len(part_prompts) - 1 else int(end_s)
            # Normaliza o prefixo "Scene N:" para refletir a ordem real (timecode/scene_idx),
            # evitando a impressão de que as cenas "estão fora de ordem" quando o template reutiliza números.
            pr_norm = re.sub(r"^Scene\s+\d+\s*:", f"Scene {scene_idx + 1}:", str(pr).strip())
            scenes.append(
                {
                    "scene_idx": scene_idx,
                    "part_id": part_id,
                    "start": _fmt_timecode(s0),
                    "end": _fmt_timecode(s1),
                    "prompt": pr_norm,
                }
            )
            scene_idx += 1

    return scenes

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


def _loads_llm_json(raw: str) -> Dict[str, Any]:
    """
    Parser defensivo: tenta parse direto; se falhar, tenta extrair o primeiro objeto JSON.
    """
    clean = _clean_json_from_llm(raw)
    try:
        return json.loads(clean)
    except Exception:
        extracted = _extract_first_json_obj(raw)
        return json.loads(extracted)


def _parse_timecode_to_s(tc: str) -> int:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(tc or ""))
    if not m:
        return 0
    return int(m.group(1)) * 60 + int(m.group(2))


def _normalize_scenes_with_timing(
    scenes: List[Dict[str, Any]],
    timing: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Garante consistência:
    - ordena por start time
    - renumera "Scene N:" em ordem sequencial
    - corrige part_id com base no intervalo do timing (evita cenas presas no hook)
    - reatribui scene_idx sequencial
    """
    intervals: List[tuple[str, int, int]] = []
    for t in timing or []:
        pid = str(t.get("id", ""))
        if not pid or pid in ("title", "_total"):
            continue
        if "start_s" not in t or "end_s" not in t:
            continue
        try:
            intervals.append((pid, int(t["start_s"]), int(t["end_s"])))
        except Exception:
            continue

    def pick_part(start_s: int) -> str:
        for pid, a, b in intervals:
            if a <= start_s <= b:
                return pid
        return intervals[-1][0] if intervals else str((scenes[0].get("part_id") if scenes else "") or "")

    # sort by time (fallback to original scene_idx)
    ordered = sorted(
        [s for s in (scenes or []) if isinstance(s, dict)],
        key=lambda x: (_parse_timecode_to_s(x.get("start", "")), int(x.get("scene_idx", 10_000))),
    )

    out: List[Dict[str, Any]] = []
    for i, s in enumerate(ordered):
        start_s = _parse_timecode_to_s(s.get("start", ""))
        pid = pick_part(start_s)
        prompt = str(s.get("prompt", "")).strip()
        prompt = re.sub(r"^Scene\s+\d+\s*:", f"Scene {i + 1}:", prompt)
        out.append(
            {
                **s,
                "scene_idx": i,
                "part_id": pid,
                "prompt": prompt,
            }
        )
    return out


def _ollama_chat(prompt: str, *, system: str = "") -> str:
    base_url = (os.getenv("OLLAMA_BASE_URL") or "http://gpu-server-01:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL") or "llama3"
    url = f"{base_url}/api/chat"
    tok = (os.getenv("WORKSHOP_ACCESS_TOKEN") or "").strip().strip('"')
    headers = {"Authorization": f"Bearer {tok}"} if tok and "/v1/proxy/" in base_url else {}
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7},
    }
    # Quando suportado pelo Ollama, força o modelo a retornar JSON válido.
    # (Se a versão não suportar, o campo é ignorado e seguimos com parsing defensivo.)
    payload["format"] = "json"

    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=payload, timeout=120, headers=headers)
            r.raise_for_status()
            data = r.json()
            msg = data.get("message", {}) if isinstance(data, dict) else {}
            return str(msg.get("content", "")).strip()
        except Exception as e:
            last_err = e
            # backoff simples
            time.sleep(0.6 * attempt)

    raise RuntimeError(
        f"Falha ao chamar Ollama em {url} (model={model}) após 3 tentativas: {last_err}"
    )


def suggest_angles(tema: str) -> List[str]:
    use_ollama = (os.getenv("USE_OLLAMA") or "").strip() in ("1", "true", "True", "yes", "YES")
    if not use_ollama:
        return _heuristic_angles(tema)

    try:
        system = (
            "Você é um roteirista de YouTube. Gere sugestões de ângulos (PT-BR) para um vídeo. "
            "Retorne APENAS JSON."
        )
        prompt = (
            f"Tema: {tema}\n\n"
            "Retorne APENAS este JSON:\n"
            '{"angles":["...","...","...","...","..."]}\n\n'
            "Regras:\n"
            "- 5 itens\n"
            "- Cada item deve ser um ângulo claro (não um título final)\n"
            "- Varie o tipo (história, mito, guia, tendência, impacto prático)\n"
        )
        raw = _ollama_chat(prompt, system=system)
        data = _loads_llm_json(raw)
        angles = data.get("angles", [])
        if isinstance(angles, list) and len(angles) >= 3:
            return [str(a).strip() for a in angles if str(a).strip()][:8]
    except Exception as e:
        logger.warning("[script_agent] falha ao sugerir ângulos via Ollama, usando heurística: %s", e)

    return _heuristic_angles(tema)


def _template_script(tema: str, angulo: str) -> str:
    return "\n".join(
        [
            f"TÍTULO (rascunho): {tema.title()} — {angulo}",
            "",
            "ABERTURA (0:00–0:20)",
            f"- Gancho: uma pergunta provocativa ligada a {tema}.",
            f"- Promessa: o que você vai entender sobre: {angulo}.",
            "",
            "CONTEXTO (0:20–1:20)",
            f"- Definição rápida do tema: {tema}.",
            "- Por que isso importa agora (um dado, notícia ou exemplo).",
            "",
            "DESENVOLVIMENTO (1:20–6:30)",
            "- Ponto 1: explique com uma analogia simples.",
            "- Ponto 2: traga um exemplo real (evento/descoberta/caso).",
            "- Ponto 3: quebre uma objeção ou mito comum.",
            "",
            "VIRADA / INSIGHT (6:30–7:20)",
            "- Uma conclusão que muda a forma de ver o assunto.",
            "",
            "ENCERRAMENTO (7:20–7:50)",
            "- Recap em 2 frases.",
            "- CTA: peça comentário com uma pergunta específica.",
        ]
    )


def _research_block_from_youtube(youtube_context: Dict[str, Any]) -> str:
    yt = youtube_context or {}
    lines: List[str] = []
    lines.append("CONTEXTO DE PESQUISA (YouTube / trends) — use como referência, não copie:")
    if yt.get("title"):
        lines.append(f"- Título do vídeo de referência: {yt.get('title')}")
    if yt.get("video_url"):
        lines.append(f"- Link do vídeo: {yt.get('video_url')}")
    if yt.get("channel_url"):
        lines.append(f"- Canal: {yt.get('channel_url')}")
    if yt.get("views"):
        lines.append(f"- Views (aprox.): {yt.get('views')}")
    desc = (yt.get("description") or "").strip()
    if desc:
        if len(desc) > 900:
            desc = desc[:900].rstrip() + "…"
        lines.append("- Descrição no YouTube (resumo do criador):\n" + desc)
    if yt.get("notes"):
        lines.append(f"- Notas: {yt.get('notes')}")
    return "\n".join([l for l in lines if l]).strip()


def generate_script(
    tema: str,
    angulo: str,
    youtube_context: Optional[Dict[str, Any]] = None,
    *,
    duration_tier: str = DEFAULT_DURATION_TIER,
    target_narration_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    tema = (tema or "").strip()
    if not tema:
        raise ValueError(
            "tema é obrigatório: informe o tema do vídeo no request (o servidor não define tema padrão)."
        )
    angulo = (angulo or "").strip()
    if not angulo:
        angulo = suggest_angles(tema)[0]

    dcfg = resolve_duration_config(duration_tier, target_narration_seconds)
    dur_meta = _duration_response_block(dcfg)

    use_ollama = (os.getenv("USE_OLLAMA") or "").strip() in ("1", "true", "True", "yes", "YES")
    research_block = _research_block_from_youtube(youtube_context or {}) if youtube_context else ""

    if not use_ollama:
        outline = _template_outline_for_duration(tema, angulo, dcfg=dcfg)
        roteiro_base = _outline_to_text(outline)
        textos = _template_part_texts(tema, angulo, outline, research_block=research_block, dcfg=dcfg)
        timing = _allocate_timecodes(textos)
        scenes = _normalize_scenes_with_timing(_scenes_from_parts(tema, angulo, textos, timing), timing)
        return {
            "tema": tema,
            "angulo": angulo,
            "youtube_context": youtube_context or {},
            "roteiro_base": roteiro_base,
            "partes": outline,
            "textos": textos,
            "timing": timing,
            "scenes": scenes,
            "provider": "template",
            "duration": dur_meta,
        }

    system = (
        "Você é um roteirista de YouTube. Escreva em PT-BR, tom claro e envolvente. "
        "Evite enrolação. Use frases curtas. Não use emojis. "
        "Crie um roteiro em partes com IDs estáveis para aprovação humana (HITL). "
        "Além do texto, produza cenas com prompts e timecodes.\n"
        f"Duração alvo da narração: {dcfg['duration_label']}.\n"
        f"O texto falado total deve caber aproximadamente entre {dcfg['words_lo']} e {dcfg['words_hi']} palavras "
        f"(referência: ~{dcfg['wpm']} palavras/minuto em PT-BR). Não ultrapasse o máximo."
    )
    prompt = (
        f"Tema: {tema}\n"
        f"Ângulo: {angulo}\n"
        + (f"\nContexto de pesquisa (YouTube/trends):\n{research_block}\n" if research_block else "\n")
        + "\n"
        "Retorne APENAS um JSON válido (sem markdown) com este formato:\n"
        "{\n"
        '  "roteiro_base": ["[id] título da parte", "..."],\n'
        '  "partes": [{"id":"hook","title":"Abertura (gancho + promessa)"}, ...],\n'
        '  "textos": [{"id":"hook","text":"texto completo PT-BR dessa parte"}, ...],\n'
        '  "scenes": [{"part_id":"hook","start":"00:00","end":"00:15","prompt":"Scene 1: ..."}, ...]\n'
        "}\n\n"
        "- `roteiro_base`: outline ordenado com IDs.\n"
        "- `textos`: cada parte deve expandir o roteiro; inclua ao menos 1 analogia e 1 exemplo concreto no total; "
        "finalize o fechamento com uma pergunta.\n"
        f"- `scenes`: entre {dcfg['scene_lo']} e {dcfg['scene_hi']} cenas; `prompt` em INGLÊS; "
        "cada prompt deve descrever um visual concreto e pesquisável (objetos, ambiente, fauna, locais) "
        "que pertença claramente ao tema e ao ângulo — evite frases genéricas como "
        "'dramatic highlight' ou 'human element' sem dizer o que aparece em cena; "
        "incluir timecodes de entrada/saída coerentes com a duração alvo; "
        "inclua: " + DEFAULT_STYLE_GUIDE
    )

    try:
        raw = _ollama_chat(prompt, system=system)
        if not raw:
            raise RuntimeError("resposta vazia do Ollama")
        data = _loads_llm_json(raw)
        roteiro_base_list = data.get("roteiro_base", [])
        partes = data.get("partes", [])
        textos = data.get("textos", [])
        scenes = data.get("scenes", [])

        if not isinstance(partes, list) or not partes:
            partes = _template_outline(tema, angulo)
        if not isinstance(textos, list) or not textos:
            textos = _template_part_texts(tema, angulo, partes, research_block=research_block)

        if not isinstance(roteiro_base_list, list) or not roteiro_base_list:
            roteiro_base = _outline_to_text(partes)
        else:
            roteiro_base = "\n".join([str(x) for x in roteiro_base_list if str(x).strip()]) or _outline_to_text(partes)

        timing = _allocate_timecodes(textos)
        if not isinstance(scenes, list) or not scenes:
            scenes = _scenes_from_parts(tema, angulo, textos, timing)
        scenes = _normalize_scenes_with_timing(scenes, timing)

        return {
            "tema": tema,
            "angulo": angulo,
            "youtube_context": youtube_context or {},
            "roteiro_base": roteiro_base,
            "partes": partes,
            "textos": textos,
            "timing": timing,
            "scenes": scenes,
            "provider": "ollama",
            "duration": dur_meta,
        }
    except Exception as e:
        logger.warning("[script_agent] falha no Ollama, usando template: %s", e)
        outline = _template_outline_for_duration(tema, angulo, dcfg=dcfg)
        roteiro_base = _outline_to_text(outline)
        textos = _template_part_texts(tema, angulo, outline, research_block=research_block, dcfg=dcfg)
        timing = _allocate_timecodes(textos)
        scenes = _normalize_scenes_with_timing(_scenes_from_parts(tema, angulo, textos, timing), timing)
        return {
            "tema": tema,
            "angulo": angulo,
            "youtube_context": youtube_context or {},
            "roteiro_base": roteiro_base,
            "partes": outline,
            "textos": textos,
            "timing": timing,
            "scenes": scenes,
            "provider": "template_fallback",
            "error": str(e),
            "duration": dur_meta,
        }


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--tema", default="", help="obrigatório: tema central do vídeo")
    parser.add_argument("--angulo", default="", help="ex: mitos sobre buracos negros")
    parser.add_argument("--listar-angulos", action="store_true", help="lista ângulos sugeridos e sai")
    parser.add_argument("--json", action="store_true", help="imprime JSON ao invés de texto")
    parser.add_argument(
        "--duration-tier",
        default=DEFAULT_DURATION_TIER,
        choices=sorted(_DURATION_TIERS),
        help="Perfil de duração da narração (custom exige --target-narration-minutes).",
    )
    parser.add_argument(
        "--target-narration-minutes",
        type=float,
        default=None,
        help="Obrigatório se --duration-tier=custom (1–60).",
    )
    args = parser.parse_args()
    if args.duration_tier == "custom" and args.target_narration_minutes is None:
        parser.error("--target-narration-minutes é obrigatório quando --duration-tier=custom")

    if args.listar_angulos:
        print("\n".join([f"- {a}" for a in suggest_angles(args.tema)]))
        return

    if not (args.tema or "").strip():
        parser.error("--tema é obrigatório ao gerar roteiro (defina o tema do vídeo).")

    result = generate_script(
        args.tema,
        args.angulo,
        duration_tier=args.duration_tier,
        target_narration_seconds=(
            int(round(float(args.target_narration_minutes) * 60))
            if args.duration_tier == "custom" and args.target_narration_minutes is not None
            else None
        ),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Tema: {result['tema']}")
    print(f"Ângulo: {result['angulo']}")
    print(f"Provider: {result['provider']}\n")

    roteiro_base = str(result.get("roteiro_base", "")).strip()
    if roteiro_base:
        print(roteiro_base)

    textos = result.get("textos") or []
    if isinstance(textos, list) and textos:
        print("\nTEXTOS POR PARTE (indexados)\n")
        for p in textos:
            pid = str(p.get("id", "")).strip()
            text = str(p.get("text", "")).strip()
            if not pid or not text:
                continue
            print(f"[{pid}]\n{text}\n")

    scenes = result.get("scenes") or []
    if isinstance(scenes, list) and scenes:
        print("\nSCENES (prompts + timing)\n")
        for s in scenes:
            try:
                idx = int(s.get("scene_idx", 0)) + 1
            except Exception:
                idx = "?"
            part_id = str(s.get("part_id", "")).strip()
            start = str(s.get("start", "")).strip()
            end = str(s.get("end", "")).strip()
            prompt = str(s.get("prompt", "")).strip()
            print(f"{idx:02d}. [{start}–{end}] part={part_id}\n    {prompt}\n")


if __name__ == "__main__":
    main()

