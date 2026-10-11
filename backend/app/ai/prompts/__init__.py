import re

_MAX_UNTRUSTED_CHARS = 4000


def sanitize_untrusted(text: str, max_chars: int = _MAX_UNTRUSTED_CHARS) -> str:
    """Make author-supplied text safe to embed inside our delimiter tags.

    Angle brackets are neutralised so the text cannot close/open our tags or forge section headers,
    and control characters are dropped. The text is still *data*; the prompts also say so explicitly.
    """
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text or "")
    cleaned = cleaned.replace("<", "‹").replace(">", "›")
    cleaned = re.sub(r"={3,}", "==", cleaned)
    return cleaned[:max_chars].strip()
