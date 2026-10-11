"""Post-generation validation: flag figures in a draft that appear in no trusted source."""
import re
from dataclasses import dataclass

_AMOUNT = re.compile(r"(?:₹|Rs\.?|INR)\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_ISBN = re.compile(r"\b97[89][-\s]?\d[-\d\s]{9,15}\d\b")


def _normalise_amount(raw: str) -> str:
    value = raw.replace(",", "")
    return value.rstrip("0").rstrip(".") if "." in value else value


def _digits(raw: str) -> str:
    return re.sub(r"\D", "", raw)


@dataclass(frozen=True)
class GroundingReport:
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.warnings


def check_grounding(draft: str, *trusted_sources: str) -> GroundingReport:
    """Every ₹ amount and ISBN in `draft` must appear in the trusted text (account data, KB policy); figures an author claims are not trusted."""
    corpus = "\n".join(trusted_sources)
    trusted_amounts = {_normalise_amount(m.group(1)) for m in _AMOUNT.finditer(corpus)}
    trusted_amounts |= {_normalise_amount(m) for m in re.findall(r"(?<![\d.])(\d[\d,]*(?:\.\d+)?)(?![\d])", corpus)}
    trusted_isbns = {_digits(m.group(0)) for m in _ISBN.finditer(corpus)}

    warnings: list[str] = []
    for match in _AMOUNT.finditer(draft):
        if _normalise_amount(match.group(1)) not in trusted_amounts:
            warnings.append(f"Amount {match.group(0).strip()} is not present in the account data or policy.")
    for match in _ISBN.finditer(draft):
        if _digits(match.group(0)) not in trusted_isbns:
            warnings.append(f"ISBN {match.group(0).strip()} is not present in the account data.")
    return GroundingReport(sorted(set(warnings)))
