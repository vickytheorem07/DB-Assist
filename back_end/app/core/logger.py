import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = os.getenv("LOG_FILE", "app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOG_FORMAT = "%(asctime)s - [RequestID: %(request_id)s] - %(filename)s:%(lineno)s - %(funcName)20s() - %(levelname)s - %(message)s"

_BASE = "app"
_configured = False


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "N/A"
        return True


def _configure():
    global _configured

    if _configured:
        return

    os.makedirs(LOG_DIR, exist_ok=True)

    base = logging.getLogger(_BASE)
    base.setLevel(LOG_LEVEL)
    base.propagate = False

    formatter = logging.Formatter(LOG_FORMAT)

    for handler in (
        logging.StreamHandler(),
        RotatingFileHandler(
            os.path.join(LOG_DIR, LOG_FILE),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
    ):
        handler.setFormatter(formatter)
        handler.addFilter(RequestIdFilter())
        base.addHandler(handler)

    _configured = True

def setup_logger(name, request_id="N/A"):
    _configure()

    return logging.LoggerAdapter(
        logging.getLogger(f"{_BASE}.{name}"),
        {"request_id": request_id}
    )
