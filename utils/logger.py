"""
utils/logger.py — Colored, structured logger for Delulu Her.
"""

import logging
import sys
import colorlog
import config


def get_logger(name: str) -> logging.Logger:
    """Return a configured colored logger for the given module name."""
    logger = logging.getLogger(name)

    if logger.handlers:  # Avoid duplicate handlers on re-import
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    handler = colorlog.StreamHandler(sys.stdout)
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s[%(asctime)s] %(name)s %(levelname)s%(reset)s  %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG":    "cyan",
                "INFO":     "green",
                "WARNING":  "yellow",
                "ERROR":    "red",
                "CRITICAL": "bold_red",
            },
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
