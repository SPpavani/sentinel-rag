"""Typed data models. Money is always Decimal, never float."""
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    line: int
    sku: str
    description: str
    serial: str
    qty: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)

    @property
    def line_total(self) -> Decimal:
        return self.qty * self.unit_price


class PurchaseOrder(BaseModel):
    po_number: Optional[str] = None
    supplier: Optional[str] = None
    ship_to: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_total: Optional[Decimal] = None
    line_items: List[LineItem] = Field(default_factory=list)

    @property
    def lines_total(self) -> Decimal:
        return sum((item.line_total for item in self.line_items), Decimal("0"))


Severity = Literal["error", "warning", "info"]


class Finding(BaseModel):
    code: str
    severity: Severity
    message: str
    line: Optional[int] = None


class VerificationReport(BaseModel):
    status: Literal["PASS", "REVIEW", "FAIL"]
    findings: List[Finding] = Field(default_factory=list)

    def by_severity(self, severity: Severity) -> List[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def has(self, code: str) -> bool:
        return any(f.code == code for f in self.findings)


class Attempt(BaseModel):
    """One round of the self-correcting loop."""

    number: int
    status: str                      # PASS | REVIEW | FAIL | UNPARSEABLE
    error_count: int = 0             # all errors found by the verifier
    extraction_errors: int = 0       # errors the model can fix by re-reading the document
    error_codes: List[str] = Field(default_factory=list)
    detail: Optional[str] = None


class ProcessingResult(BaseModel):
    extractor: str
    po: PurchaseOrder
    report: VerificationReport
    attempts: List[Attempt] = Field(default_factory=list)
    healed: bool = False             # first attempt had fixable errors, the final result has none
