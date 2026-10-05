from pathlib import Path

from app.infrastructure.logging import configure_logging


def test_configure_logging_creates_app_log_and_is_idempotent(tmp_path):
    log_path = tmp_path / "logs" / "app.log"
    logger = configure_logging(str(log_path))
    logger.info("logging-contract-test")
    logger_again = configure_logging(str(log_path))
    logger_again.info("logging-contract-test-2")

    assert log_path.exists()
    text = log_path.read_text(encoding="utf-8")
    assert "logging-contract-test" in text
    assert "logging-contract-test-2" in text
    matching = [h for h in logger.handlers if getattr(h, "baseFilename", None) == str(Path(log_path).resolve())]
    assert len(matching) == 1
