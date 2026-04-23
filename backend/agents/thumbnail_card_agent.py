"""thumbnail_card_agent — gera thumbnail (card) a partir de um frame do vídeo final.

MVP fase 1:
- Seleciona um frame do vídeo (percentual do tempo) via ffmpeg.
- Aplica template simples (default: logo_brand) via Pillow.
- Permite override por upload (quando `thumbnail.mode == "uploaded"` e `thumbnail.upload_path` existir).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from workshop.backend.core.state import VideoState

logger = logging.getLogger(__name__)

THUMB_W = 1280
THUMB_H = 720

TEMPLATE_ALIASES = {
    # UI do lab (primeira versão) → templates do publish_experiments (CTR)
    "big_title_left": "split_layout",
    "big_title_bottom": "impact_number",
    "badge_corner": "impact_number",
    "face_reaction": "arrow_focus",
}


def _safe_mkdir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


def _ffprobe_duration_s(video_path: str) -> Optional[float]:
    try:
        p = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if p.returncode != 0:
            return None
        s = (p.stdout or "").strip()
        return float(s) if s else None
    except Exception:
        return None


def _extract_frame(video_path: str, *, out_path: str, time_s: float) -> bool:
    try:
        _safe_mkdir(os.path.dirname(out_path))
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(max(0.0, time_s)),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            out_path,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return os.path.isfile(out_path)
    except Exception as e:
        logger.warning("[thumbnail_card_agent] falha ao extrair frame: %s", e)
        return False


def _paste_logo_optional(img: Image.Image, logo_path: str, *, xy: Tuple[int, int] = (40, 40)) -> None:
    """Sobreposta ao canto superior-esquerdo quando ``logo_path`` existe."""
    lp = str(logo_path or "").strip()
    if not lp or not os.path.isfile(lp):
        return
    try:
        logo = Image.open(lp).convert("RGBA")
        max_lw, max_lh = 240, 120
        lw, lh = logo.size
        scale = min(max_lw / max(1, lw), max_lh / max(1, lh), 1.0)
        logo = logo.resize((int(lw * scale), int(lh * scale)), Image.LANCZOS)
        img.paste(logo, xy, logo)
    except Exception as e:
        logger.warning("[thumbnail_card_agent] falha ao colar logo: %s", e)


def _parse_hex_color(s: str, default: Tuple[int, int, int] = (124, 92, 255)) -> Tuple[int, int, int]:
    raw = (s or "").strip()
    m = re.match(r"^#?([0-9a-fA-F]{6})$", raw)
    if not m:
        return default
    v = m.group(1)
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _env_int(name: str, default: int, *, vmin: int = 1, vmax: int = 999) -> int:
    try:
        v = int((os.getenv(name) or "").strip() or default)
        return max(vmin, min(vmax, v))
    except ValueError:
        return default


# Caminhos comuns (Linux homelab / macOS dev) — evita ImageFont.load_default() (bitmap minúsculo).
_FONT_PATHS_REGULAR: Tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
)

_FONT_PATHS_BOLD: Tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    """TrueType quando possível; último recurso bitmap (avisar no log)."""
    env_primary = (os.getenv("THUMBNAIL_FONT_BOLD_PATH" if bold else "THUMBNAIL_FONT_PATH") or "").strip()
    if env_primary and os.path.isfile(env_primary):
        try:
            return ImageFont.truetype(env_primary, size=size)
        except Exception:
            pass
    env_fallback = (os.getenv("THUMBNAIL_FONT_PATH") or "").strip()
    if bold and env_fallback and os.path.isfile(env_fallback):
        try:
            return ImageFont.truetype(env_fallback, size=size)
        except Exception:
            pass
    for path in (_FONT_PATHS_BOLD if bold else _FONT_PATHS_REGULAR):
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    try:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(name, size=size)
    except Exception:
        logger.warning(
            "[thumbnail_card_agent] sem fonte TTF adequada — usando bitmap pequeno; "
            "defina THUMBNAIL_FONT_PATH ou instale DejaVu/Liberation no servidor."
        )
        return ImageFont.load_default()


def _word_wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_w: int,
    max_lines: int,
) -> list[str]:
    words = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    if not words:
        return []
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip()
        try:
            wpx = float(draw.textlength(candidate, font=font))
        except Exception:
            wpx = float(len(candidate) * (getattr(font, "size", 12) or 12) * 0.52)
        if wpx <= max_w or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def _pick_highlight_word(line: str) -> str:
    parts = [p for p in line.split() if p]
    if not parts:
        return ""
    # Preferir número; senão última palavra.
    for p in parts:
        if re.fullmatch(r"\d[\d\.\,]*", p):
            return p
    return parts[-1]


def _shadow_text(draw: ImageDraw.ImageDraw, *, x: int, y: int, text: str, font: ImageFont.ImageFont, fill: Tuple[int, int, int]) -> None:
    # Sombra forte + contorno (estilo thumbnail agressivo)
    for dx, dy in [(4, 4), (3, 3), (2, 2)]:
        draw.text((x + dx, y + dy), text, fill=(0, 0, 0, 220), font=font)
    for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((x + dx, y + dy), text, fill=(0, 0, 0, 255), font=font)
    draw.text((x, y), text, fill=fill + (255,), font=font)


def _apply_template_youtube_growth(
    *,
    frame_path: str,
    out_path: str,
    overlay_text: str,
    template_id: str,
    brand: str = "Ideias Factory",
    logo_path: str = "",
) -> bool:
    """
    Templates inspirados em `workshop/publish_experiments/card_render.py` (CTR agressivo).
    Usa frame do vídeo como background, overlay escuro e texto curto em CAIXA ALTA.
    """
    try:
        bg = Image.open(frame_path).convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)
        img = bg.convert("RGBA")

        # overlay de legibilidade
        overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 110))
        img = Image.alpha_composite(img, overlay)
        _paste_logo_optional(img, logo_path)
        draw = ImageDraw.Draw(img)

        raw_line = " ".join(str(overlay_text or "").split())
        line = raw_line.upper()[:40].strip() or "VÍDEO"
        hw = _pick_highlight_word(line)

        grow_px = _env_int("THUMBNAIL_GROWTH_FONT_SIZE", _env_int("THUMBNAIL_TITLE_FONT_SIZE", 84))
        font_big = _load_font(grow_px, bold=True)
        font_small = _load_font(_env_int("THUMBNAIL_BRAND_LABEL_FONT_SIZE", 24), bold=False)

        margin_x = 64
        margin_y = 84
        x = margin_x
        y = margin_y

        if template_id == "split_layout":
            draw.rectangle([0, 0, int(THUMB_W * 0.52), THUMB_H], fill=(2, 6, 23, 170))
            y = margin_y + 20

        base_yellow = (250, 204, 21)
        accent_red = (239, 68, 68)

        parts = line.split()
        if hw and hw in parts:
            cur_x = x
            for w in parts:
                bbox = draw.textbbox((0, 0), w + " ", font=font_big)
                color = accent_red if w == hw else base_yellow
                _shadow_text(draw, x=cur_x, y=y, text=w, font=font_big, fill=color)
                cur_x += (bbox[2] - bbox[0])
        else:
            _shadow_text(draw, x=x, y=y, text=line, font=font_big, fill=base_yellow)

        if template_id == "impact_number":
            m = re.search(r"\b\d[\d\.\,]*\b", line)
            if m:
                badge = m.group(0)
                bx, by = 48, 44
                draw.rounded_rectangle([bx, by, bx + 220, by + 110], radius=18, fill=(239, 68, 68, 230))
                f_badge = _load_font(_env_int("THUMBNAIL_GROWTH_BADGE_FONT_SIZE", 52), bold=True)
                draw.text((bx + 20, by + 24), badge, fill=(255, 255, 255, 255), font=f_badge)

        if template_id == "arrow_focus":
            ax = int(THUMB_W * 0.78)
            ay = int(THUMB_H * 0.62)
            draw.polygon(
                [
                    (ax, ay),
                    (ax + 90, ay - 40),
                    (ax + 72, ay - 8),
                    (ax + 160, ay - 10),
                    (ax + 160, ay + 20),
                    (ax + 72, ay + 18),
                    (ax + 90, ay + 50),
                ],
                fill=(239, 68, 68, 230),
            )

        # brand footer
        bx = draw.textbbox((0, 0), brand, font=font_small)
        draw.text(((THUMB_W - (bx[2] - bx[0])) // 2, THUMB_H - 72), brand, fill=(148, 163, 184, 255), font=font_small)

        _safe_mkdir(os.path.dirname(out_path))
        img.convert("RGB").save(out_path, format="PNG", optimize=True)
        return os.path.isfile(out_path)
    except Exception as e:
        logger.warning("[thumbnail_card_agent] falha ao renderizar template growth: %s", e)
        return False


def _draw_multiline_title(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    box: Tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
    stroke_fill: Tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 4,
) -> None:
    x0, y0, x1, y1 = box
    max_w = max(1, x1 - x0)
    words = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    if not words:
        return

    lines = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip()
        wpx = draw.textlength(candidate, font=font)
        if wpx <= max_w or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
        if len(lines) >= 4:
            break
    if cur and len(lines) < 5:
        lines.append(cur)

    line_h = int(font.size * 1.15) if hasattr(font, "size") else 28
    total_h = line_h * len(lines)
    y = y0 + max(0, (y1 - y0 - total_h) // 2)
    for ln in lines:
        draw.text(
            (x0, y),
            ln,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        y += line_h


def _apply_template_logo_brand(
    *,
    frame_path: str,
    out_path: str,
    title: str,
    brand_color: Tuple[int, int, int],
    logo_path: str,
) -> bool:
    try:
        img = Image.open(frame_path).convert("RGB")
        # cover crop para 16:9
        iw, ih = img.size
        target_ar = THUMB_W / THUMB_H
        ar = iw / ih if ih else target_ar
        if ar > target_ar:
            # crop largura
            new_w = int(ih * target_ar)
            x0 = max(0, (iw - new_w) // 2)
            img = img.crop((x0, 0, x0 + new_w, ih))
        else:
            # crop altura
            new_h = int(iw / target_ar)
            y0 = max(0, (ih - new_h) // 2)
            img = img.crop((0, y0, iw, y0 + new_h))
        img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)

        # overlay gradiente (simples)
        overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(THUMB_H):
            a = int(180 * (y / THUMB_H))
            od.line([(0, y), (THUMB_W, y)], fill=(0, 0, 0, a))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGBA")

        draw = ImageDraw.Draw(img)

        _paste_logo_optional(img, logo_path)

        # faixa/acento
        draw.rounded_rectangle((36, THUMB_H - 220, 50, THUMB_H - 40), radius=8, fill=brand_color + (255,))

        # título — encaixa no box reduzindo pt gradualmente (evita texto “miúdo” por fallback bitmap / overflow).
        box = (70, THUMB_H - 250, THUMB_W - 60, THUMB_H - 30)
        x0, y0, x1, y1 = box
        max_w = max(1, x1 - x0)
        max_h = max(1, y1 - y0)
        max_lines = _env_int("THUMBNAIL_TITLE_MAX_LINES", 4)
        stroke_w = _env_int("THUMBNAIL_TITLE_STROKE_WIDTH", 5)
        start_sz = _env_int("THUMBNAIL_LOGO_BRAND_FONT_SIZE", _env_int("THUMBNAIL_TITLE_FONT_SIZE", 72))
        min_sz = _env_int("THUMBNAIL_TITLE_FONT_MIN_SIZE", 32)
        chosen_font = _load_font(min_sz, bold=True)
        chosen_lines: list[str] = []
        for size in range(start_sz, min_sz - 1, -4):
            font_try = _load_font(size, bold=True)
            lines_try = _word_wrap_lines(draw, title, font_try, max_w, max_lines)
            if not lines_try:
                continue
            line_h = int(size * 1.15)
            total_h = line_h * len(lines_try)
            if total_h <= max_h:
                chosen_font = font_try
                chosen_lines = lines_try
                break
        else:
            chosen_font = _load_font(min_sz, bold=True)
            chosen_lines = _word_wrap_lines(draw, title, chosen_font, max_w, max_lines)

        sz = int(getattr(chosen_font, "size", min_sz) or min_sz)
        line_h = int(sz * 1.15)
        total_h = line_h * len(chosen_lines)
        y = y0 + max(0, (max_h - total_h) // 2)
        for ln in chosen_lines:
            draw.text(
                (x0, y),
                ln,
                font=chosen_font,
                fill=(245, 247, 255),
                stroke_width=stroke_w,
                stroke_fill=(0, 0, 0),
            )
            y += line_h

        _safe_mkdir(os.path.dirname(out_path))
        img.convert("RGB").save(out_path, format="PNG", optimize=True)
        return os.path.isfile(out_path)
    except Exception as e:
        logger.warning("[thumbnail_card_agent] falha ao renderizar template: %s", e)
        return False


def thumbnail_card_agent(state: VideoState) -> VideoState:
    job_path = str(state.get("job_path") or "").strip()
    video_file = str(state.get("video_file") or "").strip()
    meta = state.get("metadata") or {}
    thumbnail: Dict[str, Any] = dict(state.get("thumbnail") or {})

    if not job_path:
        return {**state, "thumbnail": {**thumbnail, "status": "error", "detail": "job_path vazio"}}

    out_path = os.path.join(job_path, "thumbnail.png")
    thumb_dir = os.path.join(job_path, "thumbnail")
    _safe_mkdir(thumb_dir)

    mode = str(thumbnail.get("mode") or os.getenv("THUMBNAIL_MODE") or "auto_template").strip()

    # Modo upload (se existir)
    if mode == "uploaded":
        up = str(thumbnail.get("upload_path") or "").strip()
        if up and os.path.isfile(up):
            try:
                img = Image.open(up).convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)
                img.save(out_path, format="PNG", optimize=True)
                return {
                    **state,
                    "thumbnail": {
                        **thumbnail,
                        "mode": "uploaded",
                        "output_path": out_path,
                        "status": "draft",
                    },
                }
            except Exception as e:
                logger.warning("[thumbnail_card_agent] falha ao usar upload: %s", e)

    # auto_template
    if not video_file or not os.path.isfile(video_file):
        logger.warning("[thumbnail_card_agent] video_file ausente — não gera thumbnail")
        return {**state, "thumbnail": {**thumbnail, "mode": "auto_template", "output_path": "", "status": "skipped"}}

    dur = _ffprobe_duration_s(video_file) or 0.0
    pct = float(os.getenv("THUMBNAIL_FRAME_PCT", "0.20"))
    time_s = max(0.0, dur * min(max(pct, 0.05), 0.95)) if dur > 0 else 1.0
    frame_path = os.path.join(thumb_dir, "frame.jpg")
    ok_frame = _extract_frame(video_file, out_path=frame_path, time_s=time_s)
    if not ok_frame:
        return {**state, "thumbnail": {**thumbnail, "mode": "auto_template", "output_path": "", "status": "error"}}

    template_id = str(thumbnail.get("template_id") or os.getenv("THUMBNAIL_TEMPLATE_ID") or "logo_brand").strip()
    template_id = TEMPLATE_ALIASES.get(template_id, template_id)
    title = str(meta.get("title") or state.get("topic") or "Vídeo").strip()
    brand_hex = str(thumbnail.get("fields", {}).get("brand_color") if isinstance(thumbnail.get("fields"), dict) else "") or (
        os.getenv("THUMBNAIL_BRAND_COLOR") or "#7c5cff"
    )
    brand_color = _parse_hex_color(brand_hex)
    logo_path = str(
        (thumbnail.get("fields", {}).get("logo_path") if isinstance(thumbnail.get("fields"), dict) else "")
        or os.getenv("THUMBNAIL_LOGO_PATH")
        or ""
    ).strip()

    rendered = False
    if template_id == "logo_brand":
        rendered = _apply_template_logo_brand(
            frame_path=frame_path,
            out_path=out_path,
            title=title,
            brand_color=brand_color,
            logo_path=logo_path,
        )
    elif template_id in ("impact_number", "split_layout", "arrow_focus"):
        rendered = _apply_template_youtube_growth(
            frame_path=frame_path,
            out_path=out_path,
            overlay_text=title,
            template_id=template_id,
            logo_path=logo_path,
        )
    else:
        # fallback: usa logo_brand
        rendered = _apply_template_logo_brand(
            frame_path=frame_path,
            out_path=out_path,
            title=title,
            brand_color=brand_color,
            logo_path=logo_path,
        )
        template_id = "logo_brand"

    if not rendered:
        return {**state, "thumbnail": {**thumbnail, "mode": "auto_template", "output_path": "", "status": "error"}}

    return {
        **state,
        "thumbnail": {
            **thumbnail,
            "mode": "auto_template",
            "template_id": template_id,
            "fields": {
                **(thumbnail.get("fields") if isinstance(thumbnail.get("fields"), dict) else {}),
                "brand_color": brand_hex,
                "logo_path": logo_path,
                "title": title,
            },
            "frame": {"strategy": "pct", "frame_time_s": int(round(time_s)), "frame_path": frame_path},
            "output_path": out_path,
            "status": "draft",
        },
    }

