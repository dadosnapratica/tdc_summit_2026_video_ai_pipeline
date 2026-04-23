"""
Experimento inicial: Google Trends via pytrends.

Objetivo: gerar um payload que complemente o research_agent (YouTube Data API)
com sinais de tendência do Google.

Contexto 404 (2025): Google alterou rotas não documentadas; a comunidade reporta
falhas em massa (p.ex. `GeneralMills/pytrends#638`). Este módulo aplica workarounds
leves no cookie NID (``/trends/?geo=`` + User-Agent, padrão ``pytrends-modern``).
Não buscamos mais lista diária/hottrends (instável); só ``interest_over_time`` e
``related_queries``. Alternativas: ``trendspy``, ``pytrends-modern``.

Uso:
  python -m workshop.arm.research_agent.providers.pytrends_experiment --kw "astronomia" --geo BR --days 7
  (ou a partir da raiz do repo: ficheiro em workshop/arm/research_agent/providers/pytrends_experiment.py)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from pytrends.request import TrendReq


logger = logging.getLogger(__name__)

# pandas FutureWarning dentro do pytrends (fillna/ffill em DataFrames); não é bug nosso.
warnings.filterwarnings("ignore", category=FutureWarning, module="pytrends.request")

# Workarounds 404 / bloqueio (Google mudou rotas; ver GeneralMills/pytrends#638, fev/2025).
_PYTRENDS_GETCOOKIE_PATCHED = False

_DEFAULT_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _trend_req_requests_args(hl: str) -> Dict[str, Any]:
    """Só User-Agent extra (``accept-language`` já vem de ``hl`` no TrendReq)."""
    _ = hl  # reservado para overrides futuros
    ua = os.getenv("PYTRENDS_USER_AGENT", "").strip() or _DEFAULT_CHROME_UA
    return {"headers": {"User-Agent": ua}}


def _ensure_pytrends_getcookie_workaround() -> None:
    """
    Monkeypatch leve em TrendReq.GetGoogleCookie.

    Motivação (comunidade / forks):
    - O pytrends chama só ``/trends/explore/?geo=XX`` sem User-Agent; vários IPs recebem 404.
    - pytrends-modern obtém NID via ``/trends/?geo=XX`` e envia User-Agent no GET do cookie.

    Desligar: PYTRENDS_DISABLE_GETCOOKIE_PATCH=1
    """
    global _PYTRENDS_GETCOOKIE_PATCHED
    if _PYTRENDS_GETCOOKIE_PATCHED:
        return
    _PYTRENDS_GETCOOKIE_PATCHED = True
    if os.getenv("PYTRENDS_DISABLE_GETCOOKIE_PATCH", "").strip().lower() in ("1", "true", "yes"):
        return

    import pytrends.request as pr

    def _cookie_request_kwargs(self, proxy: Optional[Dict[str, str]]) -> Dict[str, Any]:
        kwargs = dict(self.requests_args)
        if proxy:
            kwargs["proxies"] = proxy
        kwargs["timeout"] = self.timeout
        h: Dict[str, str] = {
            "User-Agent": os.getenv("PYTRENDS_USER_AGENT", "").strip() or _DEFAULT_CHROME_UA,
        }
        h.update(getattr(self, "headers", {}) or {})
        extra = kwargs.pop("headers", None)
        if isinstance(extra, dict):
            h.update(extra)
        # Sobrescreve Accept: página HTML do Trends (self.headers pode trazer */* da API).
        h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        kwargs["headers"] = h
        return kwargs

    def GetGoogleCookie(self):  # noqa: N802 — nome legado da API pytrends
        geo = self.hl[-2:] if isinstance(self.hl, str) and len(self.hl) >= 2 else "US"
        urls = (
            f"{pr.BASE_TRENDS_URL}/?geo={geo}",
            f"{pr.BASE_TRENDS_URL}/explore/?geo={geo}",
            f"{pr.BASE_TRENDS_URL}/explore/",
        )

        def _nid_from_urls(proxy: Optional[Dict[str, str]]) -> Dict[str, str]:
            kw = _cookie_request_kwargs(self, proxy)
            for url in urls:
                try:
                    r = requests.get(url, **kw)
                    if r.status_code != 200:
                        continue
                    nid = dict(filter(lambda i: i[0] == "NID", r.cookies.items()))
                    if nid:
                        return nid
                except Exception:
                    continue
            return {}

        while True:
            if "proxies" in self.requests_args:
                try:
                    return _nid_from_urls(None)
                except Exception:
                    continue
            else:
                if len(self.proxies) > 0:
                    proxy = {"https": self.proxies[self.proxy_index]}
                else:
                    proxy = None
                try:
                    return _nid_from_urls(proxy)
                except requests.exceptions.ProxyError:
                    if len(self.proxies) > 1:
                        self.proxies.remove(self.proxies[self.proxy_index])
                    else:
                        raise
                    continue

    pr.TrendReq.GetGoogleCookie = GetGoogleCookie
    logger.debug("[pytrends] workaround GetGoogleCookie instalado (URLs alternativas + User-Agent)")


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _json_safe(obj: Any) -> Any:
    """
    Converte estruturas do pandas/pytrends para JSON serializável.
    - Índices Timestamp viram ISO strings
    - DataFrame/Series viram listas/dicts simples
    - Chaves não-string viram string
    """
    # 1) pandas.Timestamp / datetime-like (best-effort)
    iso = getattr(obj, "isoformat", None)
    if callable(iso):
        try:
            return obj.isoformat()
        except Exception:
            pass

    # 2) pandas DataFrame
    if hasattr(obj, "to_dict") and hasattr(obj, "columns") and hasattr(obj, "index"):
        try:
            # records é mais estável que to_dict() (evita chaves Timestamp)
            records = obj.reset_index().to_dict(orient="records")
            return _json_safe(records)
        except Exception:
            try:
                return _json_safe(obj.to_dict())
            except Exception:
                return str(obj)

    # 3) pandas Series
    if hasattr(obj, "to_dict") and hasattr(obj, "index") and not hasattr(obj, "columns"):
        try:
            d = obj.to_dict()
            return _json_safe(d)
        except Exception:
            return str(obj)

    # 4) dict
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            try:
                sk = k if isinstance(k, (str, int, float, bool)) or k is None else str(k)
            except Exception:
                sk = str(k)
            out[str(sk)] = _json_safe(v)
        return out

    # 5) list/tuple
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]

    # 6) primitives
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # 7) fallback
    return str(obj)


@dataclass(frozen=True)
class TrendsConfig:
    hl: str = "pt-BR"
    tz: int = -180  # minutos (Brasil ~ UTC-3)
    geo: str = "BR"
    days: int = 7

    @property
    def timeframe(self) -> str:
        # Ex: "now 7-d"
        return f"now {int(self.days)}-d"


def plot_interest_over_time(
    payload: Dict[str, Any],
    *,
    out_path: str | None = None,
    show: bool = False,
) -> None:
    """
    Plota `interest_over_time` (se disponível) para os termos consultados.
    Espera a forma serializada do payload (lista de records).
    """
    # Evita warnings/erros quando o default (~/.matplotlib) não é gravável.
    if not os.getenv("MPLCONFIGDIR"):
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mplconfig-")

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "matplotlib não está instalado. Instale com `pip install matplotlib`."
        ) from e

    records = payload.get("interest_over_time")
    if not isinstance(records, list) or not records:
        logger.warning("[pytrends] sem dados em interest_over_time para plotar")
        return

    # Detecta campo de data vindo de reset_index(): tipicamente "date" ou "index".
    date_key = "date" if "date" in records[0] else ("index" if "index" in records[0] else None)
    if date_key is None:
        logger.warning("[pytrends] não encontrei coluna de data em interest_over_time")
        return

    keywords = payload.get("keywords") or []
    if not isinstance(keywords, list) or not keywords:
        # fallback: plota todas as colunas numéricas (exceto isPartial/date)
        keywords = [
            k
            for k in records[0].keys()
            if k not in (date_key, "isPartial") and isinstance(records[0].get(k), (int, float))
        ]

    # Parse best-effort de datas ISO para datetime; se falhar, mantém string.
    from datetime import datetime

    xs_dt: List[datetime] = []
    xs_fallback: List[str] = []
    for r in records:
        raw = r.get(date_key, "")
        s = str(raw)
        try:
            # ISO 8601 (pytrends/pandas costuma gerar "YYYY-MM-DD HH:MM:SS" ou "...+00:00")
            xs_dt.append(datetime.fromisoformat(s.replace("Z", "+00:00")))
        except Exception:
            xs_fallback.append(s)

    use_datetime = len(xs_dt) == len(records)
    xs = xs_dt if use_datetime else [str(r.get(date_key, "")) for r in records]

    plt.figure(figsize=(12, 5))
    for kw in keywords:
        ys = []
        for r in records:
            v = r.get(kw)
            ys.append(_safe_float(v, default=0.0))
        plt.plot(xs, ys, label=str(kw))

    plt.title(
        f"Google Trends — interest_over_time ({payload.get('geo')} • {payload.get('timeframe')})"
    )
    plt.xlabel("data")
    plt.ylabel("interesse (0-100)")

    # Eixo X legível: poucos ticks e datas formatadas.
    if use_datetime:
        try:
            import matplotlib.dates as mdates  # type: ignore

            ax = plt.gca()
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
        except Exception:
            pass
    else:
        # fallback: limita o número de rótulos quando X é string
        step = max(1, len(xs) // 8)
        plt.xticks(ticks=list(range(0, len(xs), step)), labels=[xs[i] for i in range(0, len(xs), step)])

    plt.xticks(rotation=30, ha="right")
    plt.grid(True, alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=160)
        logger.info("[pytrends] gráfico salvo em: %s", out_path)
    if show:
        plt.show()
    plt.close()


def fetch_google_trends_signals(
    keywords: List[str],
    cfg: TrendsConfig,
) -> Dict[str, Any]:
    """
    Retorna um dict pronto para ser incluído em `trending_data`.
    Não levanta exceções por falhas de rede; retorna defaults estáveis.

    ``google_trending_searches`` permanece sempre ``[]`` (feed diário regional removido).
    """
    kw_list = [k.strip() for k in keywords if k and k.strip()]
    if not kw_list:
        kw_list = ["astronomia"]

    _ensure_pytrends_getcookie_workaround()

    try:
        # retries>0 quebra com urllib3 2.x (Retry.method_whitelist removido no pytrends 4.9.2).
        pytrends = TrendReq(
            hl=cfg.hl,
            tz=cfg.tz,
            timeout=(10, 25),
            requests_args=_trend_req_requests_args(cfg.hl),
        )
    except Exception as e:
        logger.warning("[pytrends] não foi possível inicializar TrendReq: %s", e)
        return {
            "provider": "pytrends",
            "geo": cfg.geo,
            "timeframe": cfg.timeframe,
            "keywords": kw_list,
            "google_trending_searches": [],
            "interest_over_time": {},
            "related_queries": {},
            "trend_score": 0.0,
            "error": str(e),
        }

    # Lista diária/hottrends removida (endpoints instáveis / 404 frequentes).
    interest_over_time: Dict[str, Any] = {}
    related_queries: Dict[str, Any] = {}
    trend_score = 0.0

    try:
        pytrends.build_payload(kw_list, timeframe=cfg.timeframe, geo=cfg.geo)

        iot = pytrends.interest_over_time()
        interest_over_time = _json_safe(iot) if iot is not None else {}

        rq = pytrends.related_queries()
        related_queries = _json_safe(rq) if rq is not None else {}

        # Score simples: média do interesse (0..100) dos termos, ignorando "isPartial".
        try:
            # Se for DataFrame, converte primeiro
            if hasattr(iot, "columns"):
                cols = [c for c in list(iot.columns) if c != "isPartial"]
                if cols:
                    means = []
                    for c in cols:
                        try:
                            means.append(_safe_float(iot[c].mean(), 0.0))
                        except Exception:
                            continue
                    if means:
                        trend_score = float(sum(means) / len(means))
        except Exception:
            trend_score = 0.0

    except Exception as e:
        logger.warning("[pytrends] build_payload/interest/related falhou: %s", e)

    return {
        "provider": "pytrends",
        "geo": cfg.geo,
        "timeframe": cfg.timeframe,
        "keywords": kw_list,
        "google_trending_searches": [],
        "interest_over_time": interest_over_time,
        "related_queries": related_queries,
        "trend_score": trend_score,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kw", action="append", default=[], help="keyword (repita para múltiplos)")
    parser.add_argument("--geo", default="BR", help="código geo (ex: BR, US)")
    parser.add_argument("--days", type=int, default=7, help="janela em dias (ex: 7, 30, 90)")
    parser.add_argument("--hl", default="pt-BR", help="idioma/locale (ex: pt-BR)")
    parser.add_argument("--tz", type=int, default=-180, help="timezone em minutos (ex: -180)")
    parser.add_argument("--plot", action="store_true", help="gera gráfico de interest_over_time")
    parser.add_argument("--plot-out", default="", help="salva PNG (ex: /tmp/trends.png)")
    parser.add_argument("--plot-show", action="store_true", help="abre janela do matplotlib")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    cfg = TrendsConfig(hl=args.hl, tz=args.tz, geo=args.geo, days=args.days)
    payload = fetch_google_trends_signals(args.kw, cfg)
    safe_payload = _json_safe(payload)
    print(json.dumps(safe_payload, ensure_ascii=False, indent=2))

    if args.plot:
        out_path = args.plot_out.strip() or None
        plot_interest_over_time(safe_payload, out_path=out_path, show=bool(args.plot_show))


if __name__ == "__main__":
    main()

