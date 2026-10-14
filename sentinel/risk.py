"""Surface risk notes buried in the document (flags, delays, tariffs ...)
and link them to the line item they mention."""
import re
from typing import List

from sentinel.models import Finding, PurchaseOrder
from sentinel.pdf_text import normalize

RISK_RE = re.compile(
    r"\b(flagged|mismatch|sign-off|delay(?:ed)?|customs hold|tariff advisory|"
    r"recall(?:ed)?|quarantine[d]?|counterfeit|backorder(?:ed)?)\b",
    re.I,
)
# Table rows and header rows must not be glued into prose sentences
TABLE_LINE_RE = re.compile(r"^\s*(?:\d+\s+[A-Z]{2,}-\d+\s|Line\s+SKU\b)")


def _paragraphs(source_text: str) -> List[str]:
    """Prose paragraphs; every table row ends the current paragraph."""
    paragraphs: List[str] = []
    current: List[str] = []
    for line in source_text.splitlines():
        if TABLE_LINE_RE.match(line):
            if current:
                paragraphs.append(" ".join(current))
                current = []
        elif line.strip():
            current.append(line.strip())
    if current:
        paragraphs.append(" ".join(current))
    return [normalize(p) for p in paragraphs]


def find_risk_notes(source_text: str, po: PurchaseOrder) -> List[Finding]:
    findings: List[Finding] = []
    seen = set()
    for paragraph in _paragraphs(source_text):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            if not RISK_RE.search(sentence) or sentence in seen:
                continue
            seen.add(sentence)
            linked = next(
                (item for item in po.line_items if item.sku in sentence or item.serial in sentence),
                None,
            )
            if linked:
                findings.append(
                    Finding(code="item_flagged", severity="warning", line=linked.line, message=sentence)
                )
            else:
                findings.append(Finding(code="risk_note", severity="warning", message=sentence))
    return findings
