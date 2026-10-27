# ============================================================
# AeroRoute -- Centralised Logger
# File : src/utils/logger.py
# Usage: from src.utils.logger import get_logger
#        logger = get_logger(__name__)
# ============================================================
import logging
import sys
from pathlib import Path
from config.settings import settings

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger                         # avoid duplicate handlers

    logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(_LOG_DIR / "aeroroutedb.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
