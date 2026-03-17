from __future__ import annotations

import logging
from contextlib import contextmanager
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from multiprocessing import Queue
from pathlib import Path

_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(name: str = "app") -> logging.Logger:
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        import os
        _default = Path(__file__).resolve().parents[3] / "data"
        log_dir = Path(os.getenv("MOVEOD_OUTPUT_PATH", str(_default))) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

        file_handler = RotatingFileHandler(
            log_file, maxBytes=2_000_000, backupCount=3
        )
        file_handler.setFormatter(formatter)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    _LOGGERS[name] = logger
    return logger


def child_get_logger(queue: Queue, name: str = "app") -> logging.Logger:
    """Return a logger that sends records to the parent process via *queue*.

    Call this inside a subprocess — it never touches the file system directly,
    so there are no concurrent-write issues with RotatingFileHandler.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        logger.addHandler(QueueHandler(queue))
    return logger


@contextmanager
def subprocess_logger_context(name: str = "app"):
    """Context manager for the *parent* process.

    Starts a QueueListener that drains log records sent by child processes
    (via child_get_logger) into the normal parent handlers.

    Usage::

        with subprocess_logger_context("moveod") as log_queue:
            # pass log_queue to child processes
            executor.submit(worker, log_queue, ...)
    """
    parent_logger = get_logger(name)
    queue: Queue = Queue()
    listener = QueueListener(queue, *parent_logger.handlers, respect_handler_level=True)
    listener.start()
    try:
        yield queue
    finally:
        listener.stop()
