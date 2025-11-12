import logging
from logging.handlers import RotatingFileHandler
import os

def init_logger(
    name="SmartFactory",
    level=logging.INFO,
    log_file: str | None = None,
    max_bytes: int = 10*1024*1024,
    backup_count: int = 5
) -> logging.Logger:
    """
    Initialize a logger with console and optional file output.
    Rotates log file when exceeding max_bytes.
    """
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        # Avoid duplicate handlers
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s [in %(pathname)s:%(lineno)d]'
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(level)
    logger.addHandler(ch)

    # File handler
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        fh = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )
        fh.setFormatter(formatter)
        fh.setLevel(level)
        logger.addHandler(fh)

    return logger
