import enum


class Role(str, enum.Enum):
    AUTHOR = "AUTHOR"
    ADMIN = "ADMIN"


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


UNRESOLVED_STATUSES = (TicketStatus.OPEN, TicketStatus.IN_PROGRESS)


class Priority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return PRIORITY_RANK[self]


PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2, Priority.CRITICAL: 3}


class Category(str, enum.Enum):
    ROYALTY = "Royalty & Payments"
    ISBN = "ISBN & Metadata Issues"
    PRINTING = "Printing & Quality"
    DISTRIBUTION = "Distribution & Availability"
    PRODUCTION = "Book Status & Production Updates"
    GENERAL = "General Inquiry"


class DecisionSource(str, enum.Enum):
    """Who decided a category/priority value."""

    AI = "AI"          # model output (after guardrails)
    RULE = "RULE"      # deterministic fallback when AI is unavailable
    MANUAL = "MANUAL"  # admin override
    DEFAULT = "DEFAULT"


class AIStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SenderRole(str, enum.Enum):
    AUTHOR = "AUTHOR"
    ADMIN = "ADMIN"


class AIRunStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
