"""The Sentinel: checks an extraction against the source text.

It does not care who produced the extraction (regex or an LLM). Four checks:
  1. Grounding     every value must be found in the source (catches hallucination)
  2. Completeness  line numbers 1..N with no gaps, no duplicate serial numbers,
                   and as many rows as the document contains
  3. Arithmetic    sum(qty x unit price) must equal the invoice total, to the cent
  4. Risk notes    flags, delays and tariffs mentioned in the text are surfaced
"""
import re
from collections import Counter
from decimal import Decimal
from typing import List

from sentinel.models import Finding, PurchaseOrder, VerificationReport
from sentinel.pdf_text import normalize
from sentinel.risk import find_risk_notes

MONEY_RE = re.compile(r"\$?(\d[\d,]*\.\d{2})")
# a table row: line number followed by an SKU-like token (e.g. "7 GK-3302 ...")
ROW_LIKE_RE = re.compile(r"^\s*\d+\s+[A-Z]{2,}-\d+\s", re.M)

# Errors a model can fix by re-reading the document. Document-level findings
# (invoice_total_mismatch, risk notes) are deliberately NOT in this set: telling a
# model to "fix" a genuine inconsistency in the document invites it to fudge numbers.
REPAIRABLE_CODES = {
    "ungrounded_row",
    "ungrounded_field",
    "row_count_mismatch",
    "line_numbers_not_contiguous",
    "duplicate_serial",
    "no_line_items",
}


def extraction_errors(report: VerificationReport) -> List[Finding]:
    """The errors the self-correcting loop is allowed to send back to the model."""
    return [f for f in report.findings if f.severity == "error" and f.code in REPAIRABLE_CODES]


def _money_values(text: str) -> set:
    return {m.replace(",", "") for m in MONEY_RE.findall(text)}


def _fmt(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def _check_header(po: PurchaseOrder, flat: str) -> List[Finding]:
    findings: List[Finding] = []
    for name in ("po_number", "supplier", "ship_to", "invoice_number"):
        value = getattr(po, name)
        if value is None:
            findings.append(Finding(code="missing_field", severity="warning", message=f"{name} was not found"))
        elif normalize(value) not in flat:
            findings.append(
                Finding(code="ungrounded_field", severity="error",
                        message=f"{name} '{value}' does not appear in the source document")
            )
    if po.invoice_total is not None and f"{po.invoice_total:.2f}" not in _money_values(flat):
        findings.append(
            Finding(code="ungrounded_field", severity="error",
                    message=f"invoice_total {_fmt(po.invoice_total)} does not appear in the source document")
        )
    return findings


def _check_rows(po: PurchaseOrder, source_text: str) -> List[Finding]:
    """Each extracted row must exist as ONE line of the source containing all its values."""
    source_lines = [normalize(line) for line in source_text.splitlines() if line.strip()]
    findings: List[Finding] = []
    for item in po.line_items:
        grounded = False
        for line in source_lines:
            tokens = set(line.split())
            if (
                str(item.line) in tokens
                and item.sku in tokens
                and item.serial in tokens
                and str(item.qty) in tokens
                and f"{item.unit_price:.2f}" in _money_values(line)
                and normalize(item.description) in line
            ):
                grounded = True
                break
        if not grounded:
            findings.append(
                Finding(code="ungrounded_row", severity="error", line=item.line,
                        message=f"line {item.line} ({item.sku}, {item.serial}, qty {item.qty}, "
                                f"{_fmt(item.unit_price)}) does not match any row in the source")
            )
    return findings


def _check_row_count(po: PurchaseOrder, source_text: str) -> List[Finding]:
    """The source shows N table rows; a model that returns fewer has dropped some."""
    in_source = len(ROW_LIKE_RE.findall(source_text))
    if po.line_items and in_source and in_source != len(po.line_items):
        return [Finding(
            code="row_count_mismatch", severity="error",
            message=f"the document contains {in_source} table rows but {len(po.line_items)} were extracted",
        )]
    return []


def _check_completeness(po: PurchaseOrder) -> List[Finding]:
    findings: List[Finding] = []
    if not po.line_items:
        return [Finding(code="no_line_items", severity="error", message="no line items were extracted")]
    numbers = sorted(item.line for item in po.line_items)
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        findings.append(
            Finding(code="line_numbers_not_contiguous", severity="error",
                    message=f"line numbers are not 1..{len(numbers)}; missing: {missing or 'duplicates present'}")
        )
    for serial, count in Counter(item.serial for item in po.line_items).items():
        if count > 1:
            findings.append(
                Finding(code="duplicate_serial", severity="error",
                        message=f"serial {serial} appears on {count} line items")
            )
    return findings


def _check_arithmetic(po: PurchaseOrder) -> List[Finding]:
    if not po.line_items:
        return []
    if po.invoice_total is None:
        return [Finding(code="invoice_total_missing", severity="warning",
                        message="no invoice total found, so line items cannot be reconciled")]
    total = po.lines_total
    if total != po.invoice_total:
        diff = abs(total - po.invoice_total)
        label = f"invoice {po.invoice_number}" if po.invoice_number else "the invoice"
        return [Finding(
            code="invoice_total_mismatch", severity="error",
            message=(f"line items sum to {_fmt(total)} but {label} states "
                     f"{_fmt(po.invoice_total)} (difference {_fmt(diff)})"),
        )]
    return [Finding(code="invoice_total_ok", severity="info",
                    message=f"line items reconcile with the invoice total ({_fmt(total)})")]


def verify(po: PurchaseOrder, source_text: str) -> VerificationReport:
    flat = normalize(source_text)
    findings: List[Finding] = []
    findings += _check_header(po, flat)
    findings += _check_rows(po, source_text)
    findings += _check_row_count(po, source_text)
    findings += _check_completeness(po)
    findings += _check_arithmetic(po)
    findings += find_risk_notes(source_text, po)

    if any(f.severity == "error" for f in findings):
        status = "FAIL"
    elif any(f.severity == "warning" for f in findings):
        status = "REVIEW"
    else:
        status = "PASS"
    return VerificationReport(status=status, findings=findings)
