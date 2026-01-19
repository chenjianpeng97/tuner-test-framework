from __future__ import annotations

import logging
from pathlib import Path

from tuner.util.log import configure_logging, get_logger, shutdown_logging


def main() -> None:
    log_dir = Path(__file__).resolve().parent / "_logs"

    configure_logging(
        log_dir=log_dir,
        level="DEBUG",
        to_console=True,
        to_file=True,
        intercept_std_logging=True,
    )

    log = get_logger("log_example", run_id="demo-001")

    log.debug("debug message")
    log.info("info message")
    log.warning("warning message")

    try:
        1 / 0
    except ZeroDivisionError:
        log.exception("caught an exception")

    # Demonstrate stdlib logging interception.
    std = logging.getLogger("stdlib")
    std.info("this comes from stdlib logging")

    shutdown_logging()


if __name__ == "__main__":
    main()
