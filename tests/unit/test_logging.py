from __future__ import annotations

import logging
from pathlib import Path

from tuner.util.log import configure_logging, shutdown_logging


def test_configure_logging_writes_file(tmp_path: Path) -> None:
    configure_logging(
        log_dir=tmp_path,
        level="INFO",
        to_console=False,
        to_file=True,
        intercept_std_logging=False,
    )

    log = logging.getLogger("test.stdlib")
    log.setLevel(logging.INFO)

    # Not intercepted in this test; use loguru directly via stdlib wouldn't write.
    # Instead, just ensure sink exists by emitting through intercepted=False? can't.
    # We'll reconfigure with interception and then emit.
    shutdown_logging()

    configure_logging(
        log_dir=tmp_path,
        level="INFO",
        to_console=False,
        to_file=True,
        intercept_std_logging=True,
    )

    logging.getLogger("test.stdlib").info("hello from stdlib")

    shutdown_logging()

    assert any(p.suffix == ".log" for p in tmp_path.iterdir())


def test_intercept_std_logging_creates_log_file(tmp_path: Path) -> None:
    configure_logging(
        log_dir=tmp_path,
        level="DEBUG",
        to_console=False,
        to_file=True,
        intercept_std_logging=True,
    )

    logging.getLogger("some.lib").warning("warn message")
    shutdown_logging()

    log_files = list(tmp_path.glob("*.log"))
    assert log_files, "Expected at least one log file to be created"

    content = "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in log_files
    )
    assert "warn message" in content
