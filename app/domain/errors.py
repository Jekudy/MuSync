class RateLimited(Exception):
    """Operation was rate limited by provider. Includes suggested wait time in milliseconds."""

    def __init__(self, retry_after_ms: int, message: str = "Rate limited") -> None:
        super().__init__(message)
        self.retry_after_ms = retry_after_ms


class TemporaryFailure(Exception):
    """Transient provider or network failure. Retrying may succeed."""


class PermanentFailure(Exception):
    """Non-retriable failure due to invalid input or authorization issues."""


class NotFound(Exception):
    """Requested resource was not found."""


