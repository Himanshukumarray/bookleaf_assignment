"""Provider-agnostic AI failure taxonomy. Retry policy depends only on this split."""


class AIError(Exception):
    error_type = "AI_ERROR"

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.attempts = 1  # filled in by the retry wrapper


class AITransientError(AIError):
    """Timeouts, 429 and 5xx: worth retrying with backoff."""

    error_type = "TRANSIENT"


class AIPermanentError(AIError):
    """Bad credentials, invalid request, blocked content, schema failures: retrying cannot help."""

    error_type = "PERMANENT"


class AIInvalidResponseError(AIPermanentError):
    error_type = "INVALID_RESPONSE"


class AINotConfiguredError(AIPermanentError):
    error_type = "NOT_CONFIGURED"
