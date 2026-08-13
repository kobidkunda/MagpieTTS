"""Logging setup."""

import logging
import logging.handlers
import os
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_logging(level: str = "info", log_dir: Optional[str] = None,
                  max_bytes: int = 10 * 1024 * 1024, backups: int = 3,
                  log_text: bool = False) -> None:
    log_dir = log_dir or os.path.join(BASE_DIR, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s", "%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "server.log"), maxBytes=max_bytes, backupCount=backups,
        encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    logging.getLogger("magpie.request").setLevel(logging.INFO)

    if log_text:
        logging.getLogger("magpie.text").setLevel(logging.DEBUG)
