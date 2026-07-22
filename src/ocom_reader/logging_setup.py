"""Logging setup: one console handler on the package logger."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("ocom_reader")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    return logger
