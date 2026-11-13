import logging
import re


class RedactTelegramToken(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(r"(https://api\.telegram\.org/bot)[^/\s\"']+",
                            r"\1[REDACTED]", record.getMessage())
        record.msg = re.sub(r"(?<!\d)\d{6,}:[A-Za-z0-9_-]{20,}", "[REDACTED]", record.msg)
        record.args = ()
        return True


class RemoveQueryString(logging.Filter):
    """Uvicorn includes query credentials in its default request access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            args[2] = str(args[2]).split("?", 1)[0]
            record.args = tuple(args)
        return True


def protect_access_logs() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RemoveQueryString) for item in logger.filters):
        logger.addFilter(RemoveQueryString())
    for name in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, RedactTelegramToken) for item in logger.filters):
            logger.addFilter(RedactTelegramToken())
