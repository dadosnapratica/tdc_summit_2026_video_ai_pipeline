#!/usr/bin/env python3
"""
Lê workshop/nas/examples/03_assets/asset_research_scene_export.json e descarrega cada asset
para pastas scene_XX_part_<script_part_id>/ com nomes scene_XX_rank_YY.<ext>.

URLs de página (Pexels/Pixabay) → extrai URL de imagem (og:image / images.pexels.com).
URLs directas (videos.pexels.com, cdn.pixabay.com/video, ficheiros .mp4/.jpg na path) → GET directo.

Para cada linha com selected=true, grava também scene_XX_rank_YY_selected.<ext> (mesmo conteúdo).

Uso:
  python workshop/nas/download_scene_assets.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9,pt;q=0.8",
    }
)

TIMEOUT = 120
CHUNK = 256 * 1024

_CT_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}


def _norm_ct(ct: str | None) -> str | None:
    if not ct:
        return None
    return ct.split(";")[0].strip().lower()


def _ext_from_url(url: str) -> str | None:
    path = urlparse(url).path
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mov"):
        if path.lower().endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return None


def _ext_from_content_type(ct: str | None) -> str | None:
    n = _norm_ct(ct)
    if not n:
        return None
    return _CT_EXT.get(n)


def _looks_like_direct_media(url: str) -> bool:
    u = url.lower()
    if any(
        x in u
        for x in (
            "videos.pexels.com",
            "cdn.pixabay.com/video",
            "images.pexels.com",
        )
    ):
        return True
    if re.search(r"\.(jpe?g|png|webp|gif|mp4|webm|mov)(\?|$)", u):
        return True
    return False


_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_OG_IMAGE_RE2 = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.I,
)
_IMG_PEXELS_RE = re.compile(
    r"https://images\.pexels\.com/photos/[^\"'\s<>]+\.(?:jpe?g|png|webp)", re.I
)


_PIXABAY_CDN_IMG_RE = re.compile(
    r"https://cdn\.pixabay\.com/photo/[^\"'\s<>]+\.(?:jpe?g|png|webp)", re.I
)


def _extract_image_url_from_html(html: str) -> str | None:
    m = _OG_IMAGE_RE.search(html) or _OG_IMAGE_RE2.search(html)
    if m:
        return m.group(1).strip().replace("&amp;", "&")
    found = _IMG_PEXELS_RE.findall(html)
    if found:
        return max(found, key=len)
    found2 = _PIXABAY_CDN_IMG_RE.findall(html)
    if found2:
        return max(found2, key=len)
    return None


def _pexels_photo_id(url: str) -> str | None:
    """Extrai o ID numérico final das URLs /photo/...-123456/."""
    path = urlparse(url).path.rstrip("/")
    m = re.search(r"-(\d+)$", path)
    return m.group(1) if m else None


def _pexels_direct_image_url(photo_id: str) -> str:
    """Evita GET à página HTML (403 em muitos ambientes): CDN images.pexels.com."""
    return (
        f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
        "?auto=compress&cs=tinysrgb&dpr=1&w=1600"
    )


def _pixabay_page_headers() -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://pixabay.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }


def resolve_fetch_url(url: str, media_type_hint: str) -> str:
    """Devolve URL final a descarregar (bytes de imagem/vídeo)."""
    if _looks_like_direct_media(url):
        return url

    host = urlparse(url).netloc.lower()
    path = urlparse(url).path

    # Pexels: página /photo/… → tentar CDN; se 404, fallback a og:image na página.
    if "pexels.com" in host and "/photo/" in path:
        pid = _pexels_photo_id(url)
        if pid:
            du = _pexels_direct_image_url(pid)
            try:
                h = SESSION.head(du, allow_redirects=True, timeout=30)
                if h.status_code == 200:
                    return du
            except OSError:
                pass
            r = SESSION.get(
                url,
                allow_redirects=True,
                timeout=TIMEOUT,
                headers={"Referer": "https://www.pexels.com/"},
            )
            r.raise_for_status()
            ct0 = _norm_ct(r.headers.get("Content-Type"))
            if ct0 and not ct0.startswith("text/html"):
                return str(r.url)
            img = _extract_image_url_from_html(r.text)
            if img:
                return img
            return du

    # Pixabay: páginas de conteúdo (não cdn.pixabay.com) — GET com Referer.
    if "pixabay.com" in host and "cdn.pixabay.com" not in host:
        r = SESSION.get(
            url,
            allow_redirects=True,
            timeout=TIMEOUT,
            headers=_pixabay_page_headers(),
        )
        r.raise_for_status()
        ct = _norm_ct(r.headers.get("Content-Type"))
        if ct and not ct.startswith("text/html"):
            return str(r.url)
        html = r.text
        img = _extract_image_url_from_html(html)
        if not img:
            raise RuntimeError(f"Página Pixabay sem og:image: {url}")
        return img

    r = SESSION.get(url, allow_redirects=True, timeout=TIMEOUT)
    r.raise_for_status()
    ct = _norm_ct(r.headers.get("Content-Type"))
    if ct and not ct.startswith("text/html"):
        return str(r.url)

    html = r.text
    img = _extract_image_url_from_html(html)
    if not img:
        raise RuntimeError(
            f"Página sem og:image / images.pexels.com utilizável: {url}"
        )
    return img


def download_bytes(url: str) -> tuple[bytes, str | None]:
    extra: dict[str, str] = {}
    if "images.pexels.com" in url.lower():
        extra["Referer"] = "https://www.pexels.com/"
    r = SESSION.get(url, stream=True, timeout=TIMEOUT, headers=extra or None)
    r.raise_for_status()
    ct = _norm_ct(r.headers.get("Content-Type"))
    chunks: list[bytes] = []
    for part in r.iter_content(CHUNK):
        if part:
            chunks.append(part)
    return b"".join(chunks), ct


def scene_dir_name(scene_idx: int, script_part_id: str) -> str:
    n = scene_idx + 1
    safe = re.sub(r"[^\w\-]", "_", str(script_part_id).strip() or "part")
    return f"scene_{n:02d}_part_{safe}"


def pick_extension(url: str, content_type: str | None, media_type_hint: str) -> str:
    ext = _ext_from_content_type(content_type) or _ext_from_url(url)
    if ext:
        return ext
    if "video" in (media_type_hint or "").lower():
        return ".mp4"
    return ".jpg"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    nas_root = Path(__file__).resolve().parent
    json_path = nas_root / "examples" / "03_assets" / "asset_research_scene_export.json"
    if not json_path.is_file():
        logger.error("Ficheiro não encontrado: %s", json_path)
        return 1

    raw = json.loads(json_path.read_text(encoding="utf-8"))
    scenes = raw.get("scenes") or []
    base_out = nas_root / "examples" / "03_assets" / "by_scene"
    base_out.mkdir(parents=True, exist_ok=True)

    ok = 0
    err = 0
    for sc in scenes:
        scene_idx = int(sc.get("scene_idx", -1))
        script_part_id = str(sc.get("script_part_id") or "part")
        folder = base_out / scene_dir_name(scene_idx, script_part_id)
        folder.mkdir(parents=True, exist_ok=True)
        scene_num = scene_idx + 1
        for a in sc.get("assets") or []:
            rank = int(a.get("rank", 0))
            url = str(a.get("url") or "").strip()
            media_type = str(a.get("media_type") or "")
            selected = bool(a.get("selected"))
            if not url:
                logger.warning("Cena %s rank %s: URL vazia — ignorado.", scene_idx, rank)
                err += 1
                continue
            try:
                fetch_url = resolve_fetch_url(url, media_type)
                data, ct = download_bytes(fetch_url)
                ext = pick_extension(fetch_url, ct, media_type)
                stem = f"scene_{scene_num:02d}_rank_{rank:02d}"
                path_main = folder / f"{stem}{ext}"
                path_main.write_bytes(data)
                logger.info("OK %s (%s bytes) ← %s", path_main.name, len(data), fetch_url[:80])
                ok += 1
                if selected:
                    path_sel = folder / f"{stem}_selected{ext}"
                    path_sel.write_bytes(data)
                    logger.info("   → %s", path_sel.name)
            except Exception as e:
                logger.error("Falha cena %s rank %s (%s): %s", scene_idx, rank, url[:60], e)
                err += 1

    logger.info("Concluído: %s ficheiros OK, %s erros. Saída: %s", ok, err, base_out)
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
