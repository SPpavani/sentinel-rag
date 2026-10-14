"""Deterministic extractor: regular expressions over the PDF text.

It cannot hallucinate: a value is returned only if it matched the document.
Good for known, stable layouts; the LLM extractor (llm.py) handles messy ones.
"""
import re
from decimal import Decimal
from typing import List

from sentinel.models import LineItem, PurchaseOrder
from sentinel.pdf_text import normalize

PO_RE = re.compile(r"PURCHASE ORDER\s*#\s*([A-Z0-9-]+)", re.I)
SUPPLIER_RE = re.compile(r"Supplier:\s*(.+?)\s+Ship-to:")
SHIP_TO_RE = re.compile(r"Ship-to:\s*(.+?)\.\s")
INVOICE_RE = re.compile(r"Invoice\s+([A-Z]{2,5}-\d+)[^$]*?totals?\s+\$([\d,]+\.\d{2})")
# line | SKU | description | serial | qty | unit price
ROW_RE = re.compile(
    r"^\s*(\d+)\s+([A-Z]{2,}-\d+)\s+(.+?)\s+(SN-[\w-]+)\s+(\d+)\s+\$([\d,]+\.\d{2})\s*$",
    re.M,
)


def _money(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def extract_line_items(text: str) -> List[LineItem]:
    """Rows are read from the joined text, so a table split over two pages is fine.
    Repeated header rows never match because they contain no numbers."""
    return [
        LineItem(
            line=int(line),
            sku=sku,
            description=description.strip(),
            serial=serial,
            qty=int(qty),
            unit_price=_money(price),
        )
        for line, sku, description, serial, qty, price in ROW_RE.findall(text)
    ]


def extract_po(text: str) -> PurchaseOrder:
    flat = normalize(text)

    def first(pattern, source=flat, group=1):
        match = pattern.search(source)
        return match.group(group) if match else None

    invoice = INVOICE_RE.search(flat)
    return PurchaseOrder(
        po_number=first(PO_RE),
        supplier=first(SUPPLIER_RE),
        ship_to=first(SHIP_TO_RE),
        invoice_number=invoice.group(1) if invoice else None,
        invoice_total=_money(invoice.group(2)) if invoice else None,
        line_items=extract_line_items(text),
    )
