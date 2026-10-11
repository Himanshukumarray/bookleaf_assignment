from app.models.book import (
    BookAvailability,  # defined beside Book to share one mapper registry
)

__all__ = ["BookAvailability"]
