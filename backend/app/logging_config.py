import logging


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
