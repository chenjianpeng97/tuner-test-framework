"""Logging utilities for the framework.

Goals:
- Provide a single, consistent logger interface for the framework and tests.
- Use loguru for better formatting and file rotation.
- Optionally intercept stdlib `logging` so legacy code (e.g. db helpers) also shows up.

Usage:
    from tuner.util.log import configure_logging, get_logger

    configure_logging(log_dir="logs", level="DEBUG")
    log = get_logger("my-module")
    log.info("Hello")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from loguru import logger as _logger

_HANDLER_IDS: list[int] = []
_CONFIGURED: bool = False


class _InterceptHandler(logging.Handler):
    """Forward stdlib logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _logger.opt(
            depth=depth,
            exception=record.exc_info,
            ansi=False,
        ).log(level, record.getMessage())


def _normalize_log_dir(log_dir: str | Path | None) -> Path:
    if log_dir is None:
        return Path.cwd() / "logs"
    return Path(log_dir)


def configure_logging(
    *,
    log_dir: str | Path | None = None,
    level: str = "INFO",
    to_console: bool = True,
    to_file: bool = True,
    rotation: str = "10 MB",
    retention: str = "7 days",
    enqueue: bool = True,
    backtrace: bool = True,
    diagnose: bool = False,
    intercept_std_logging: bool = True,
) -> None:
    """Configure global logging sinks.

    This function is safe to call multiple times; it will remove previous sinks.

    Args:
        log_dir: Directory to place log files in.
        level: Log level (e.g. "DEBUG", "INFO").
        to_console: Enable console logging.
        to_file: Enable file logging.
        rotation: loguru rotation policy.
        retention: loguru retention policy.
        enqueue: Use multiprocessing-safe queue (recommended in real runs).
        backtrace: Show better tracebacks.
        diagnose: Include local variables in tracebacks (avoid in CI if noisy).
        intercept_std_logging: Intercept stdlib logging -> loguru.
    """

    global _CONFIGURED

    shutdown_logging()

    # Ensure default extra fields exist so formats never KeyError.
    _logger.configure(extra={"logger_name": "-"})

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[logger_name]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    if to_console:
        _HANDLER_IDS.append(
            _logger.add(
                sys.stderr,
                level=level,
                format=fmt,
                enqueue=enqueue,
                backtrace=backtrace,
                diagnose=diagnose,
            )
        )

    if to_file:
        directory = _normalize_log_dir(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        log_path = directory / "tuner_{time:YYYYMMDD}.log"
        _HANDLER_IDS.append(
            _logger.add(
                str(log_path),
                level=level,
                format=fmt,
                rotation=rotation,
                retention=retention,
                enqueue=enqueue,
                backtrace=backtrace,
                diagnose=diagnose,
                encoding="utf-8",
            )
        )

    if intercept_std_logging:
        logging.root.handlers = [_InterceptHandler()]
        logging.root.setLevel(level)
        for name in list(logging.root.manager.loggerDict.keys()):
            logging.getLogger(name).handlers = []
            logging.getLogger(name).propagate = True

    _CONFIGURED = True


def get_logger(logger_name: str | None = None, /, **extra: Any):
    """Get a logger bound with extra context.

    The returned logger is a loguru logger with fields bound.
    """

    if not _CONFIGURED:
        # Lightweight default config for interactive usage.
        configure_logging(to_file=False, intercept_std_logging=False)

    bound = _logger
    if logger_name is not None:
        bound = bound.bind(logger_name=logger_name)

    if extra:
        bound = bound.bind(**extra)

    return bound


def shutdown_logging() -> None:
    """Remove all configured sinks (useful in unit tests)."""

    global _CONFIGURED

    # Remove loguru sinks we created.
    for handler_id in _HANDLER_IDS:
        try:
            _logger.remove(handler_id)
        except Exception:
            pass
    _HANDLER_IDS.clear()

    _CONFIGURED = False
