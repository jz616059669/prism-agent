import logging
import sys
import os
from pathlib import Path
import traceback


PRISM_HOME = Path.home() / ".prism"
LOG_DIR = PRISM_HOME / "logs"
LOG_FILE = LOG_DIR / "prism.log"


def _ensure_dirs() -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def get_logger(name: str = "prism") -> logging.Logger:
    _ensure_dirs()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    try:
        fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


logger = get_logger()


def log_exception(log: logging.Logger, msg: str = "unhandled exception") -> None:
    log.debug("%s: %s", msg, traceback.format_exc())

