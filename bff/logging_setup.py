from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from workshop.backend.core.correlation import get_correlation_id


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # disponibiliza %(correlation_id)s no formatter
        record.correlation_id = get_correlation_id() or "-"
        return True


_ANSI_RESET = "\x1b[0m"
_ANSI_RED = "\x1b[31m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_CYAN = "\x1b[36m"


class ConsolePrettyFormatter(logging.Formatter):
    """
    Formato de console inspirado no padrão:
    2021-10-13 22:40:40,531 - [DEBUG] api [123] [module.func:11]: msg
    + adiciona cid=... logo após o logger
    """

    def __init__(self, *, colored: bool) -> None:
        super().__init__()
        self._colored = colored

    def format(self, record: logging.LogRecord) -> str:
        # timestamp no padrão do logging (com ms por vírgula)
        ts = self.formatTime(record, datefmt=None)
        level = (record.levelname or "").upper()
        logger_name = record.name or ""
        pid = record.process
        module = record.module or ""
        func = record.funcName or ""
        lineno = record.lineno
        cid = getattr(record, "correlation_id", "-") or "-"
        msg = record.getMessage()

        lvl = f"[{level}]"
        if self._colored:
            if record.levelno >= logging.ERROR:
                lvl = f"{_ANSI_RED}{lvl}{_ANSI_RESET}"
            elif record.levelno >= logging.WARNING:
                lvl = f"{_ANSI_YELLOW}{lvl}{_ANSI_RESET}"
            elif record.levelno >= logging.INFO:
                lvl = f"{_ANSI_GREEN}{lvl}{_ANSI_RESET}"
            else:
                lvl = f"{_ANSI_CYAN}{lvl}{_ANSI_RESET}"

        return f"{ts} - {lvl} {logger_name} cid={cid} [{pid}] [{module}.{func}:{lineno}]: {msg}"


def configure_logging() -> None:
    """
    Logging do Lab:
    - Console (stdout)
    - Arquivo com rotação diária (midnight), mantendo N dias
    """
    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    # Default: diretório local `./logs` (pensado para deploy no diretório "server").
    log_dir = Path((os.getenv("LOG_DIR") or "logs").strip()).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "lab.log"

    # formato (arquivo) inclui data/hora, nível, módulo(logger name), correlation id
    fmt = (
        "%(asctime)s %(levelname)s %(name)s "
        "cid=%(correlation_id)s "
        "%(message)s"
    )
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)

    # evita duplicar handlers em reload
    for h in list(root.handlers):
        root.removeHandler(h)

    filt = CorrelationIdFilter()

    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.addFilter(filt)
    root.addHandler(sh)

    # Console: formato "padrão de biblioteca" + cores ANSI opcionais (somente no [LEVEL]).
    # Habilitar: LOG_COLORED=1
    use_colored = (os.getenv("LOG_COLORED") or "").strip().lower() in ("1", "true", "yes")
    sh.setFormatter(ConsolePrettyFormatter(colored=use_colored))

    keep_days = int(os.getenv("LOG_KEEP_DAYS") or "14")
    fh = TimedRotatingFileHandler(
        filename=str(log_path),
        when="midnight",
        interval=1,
        backupCount=max(1, keep_days),
        encoding="utf-8",
        utc=False,
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    fh.addFilter(filt)
    root.addHandler(fh)

    # Debug log forense (somente em arquivo; potencialmente sensível).
    # Habilitar com DEBUG_TRACE_LOG=1 e reiniciar o processo.
    if (os.getenv("DEBUG_TRACE_LOG") or "").strip().lower() in ("1", "true", "yes"):
        debug_path = log_dir / "lab.debug.jsonl"
        dh = TimedRotatingFileHandler(
            filename=str(debug_path),
            when="midnight",
            interval=1,
            backupCount=max(1, keep_days),
            encoding="utf-8",
            utc=False,
        )
        # Sempre DEBUG no arquivo forense (independente do LOG_LEVEL geral).
        dh.setLevel(logging.DEBUG)
        # JSONL já vem serializado na mensagem; manter formato mínimo com timestamp + módulo + cid.
        debug_fmt = "%(asctime)s %(levelname)s %(name)s cid=%(correlation_id)s %(message)s"
        dh.setFormatter(logging.Formatter(fmt=debug_fmt, datefmt=datefmt))
        dh.addFilter(filt)
        logging.getLogger("lab_trace").setLevel(logging.DEBUG)
        logging.getLogger("lab_trace").propagate = False
        # evitar duplicar handlers no reload
        lt = logging.getLogger("lab_trace")
        for h in list(lt.handlers):
            lt.removeHandler(h)
        lt.addHandler(dh)

