from decimal import Decimal
from pathlib import Path

import pytest

from sentinel.models import LineItem, PurchaseOrder

ROOT = Path(__file__).resolve().parent.parent

CLEAN_TEXT = """PURCHASE ORDER #PO-1
Supplier: Acme Parts Ltd Ship-to: Dallas DC-1. Standard terms apply.
Line SKU Description Serial Number Qty Unit Price
1 AA-100 Widget small SN-1-A 10 $5.00
2 BB-200 Widget large SN-1-B 2 $12.50
Invoice INV-9 for this PO totals $75.00 and is due net-30.
"""


def make_po(**overrides) -> PurchaseOrder:
    data = dict(
        po_number="PO-1",
        supplier="Acme Parts Ltd",
        ship_to="Dallas DC-1",
        invoice_number="INV-9",
        invoice_total=Decimal("75.00"),
        line_items=[
            LineItem(line=1, sku="AA-100", description="Widget small", serial="SN-1-A", qty=10, unit_price=Decimal("5.00")),
            LineItem(line=2, sku="BB-200", description="Widget large", serial="SN-1-B", qty=2, unit_price=Decimal("12.50")),
        ],
    )
    data.update(overrides)
    return PurchaseOrder(**data)


@pytest.fixture
def clean_text():
    return CLEAN_TEXT


@pytest.fixture
def sample_pdf():
    return str(ROOT / "sample_po.pdf")
