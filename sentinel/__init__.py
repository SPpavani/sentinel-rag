"""Sentinel: verified extraction from procurement PDFs.

No extracted value is trusted until it is checked against the source document.
"""
from sentinel.models import Finding, LineItem, ProcessingResult, PurchaseOrder, VerificationReport
from sentinel.pipeline import process_pdf, process_text
from sentinel.verify import verify

__version__ = "0.1.0"
__all__ = [
    "Finding",
    "LineItem",
    "ProcessingResult",
    "PurchaseOrder",
    "VerificationReport",
    "process_pdf",
    "process_text",
    "verify",
]
