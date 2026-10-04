import logging
from pathlib import Path


def configure_logging(path: str = "logs/app.log"):
    """Configure the application logger with an idempotent file handler.

    Credentials must never be passed to this logger. The explicit FileHandler is
    intentional: Streamlit/pytest may already configure the root logger, making
    logging.basicConfig() ineffective.
    """
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ozon-promotion-manager")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).resolve() == log_path.resolve():
            return logger

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
