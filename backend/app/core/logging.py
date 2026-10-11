import logging
import re

_SECRET_PATTERN = re.compile(r"(AIza[0-9A-Za-z_\-]{20,}|api[_-]?key=[^&\s]+)", re.IGNORECASE)


class RedactSecretsFilter(logging.Filter):
    """Defence in depth: scrub anything that looks like an API key from log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SECRET_PATTERN.sub("[REDACTED]", str(record.msg))
        if record.args:
            record.args = tuple(_SECRET_PATTERN.sub("[REDACTED]", str(a)) if isinstance(a, str) else a for a in record.args)
        return True


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactSecretsFilter())
    logging.getLogger("httpx").setLevel(logging.WARNING)
