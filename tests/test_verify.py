from decimal import Decimal

from sentinel.models import LineItem
from sentinel.verify import verify

from conftest import make_po


def test_clean_document_passes(clean_text):
    report = verify(make_po(), clean_text)
    assert report.status == "PASS"
    assert report.has("invoice_total_ok")


def test_hallucinated_serial_is_caught(clean_text):
    bad = make_po()
    bad.line_items[1] = LineItem(line=2, sku="BB-200", description="Widget large", serial="SN-9-ZZ", qty=2, unit_price=Decimal("12.50"))
    report = verify(bad, clean_text)
    assert report.status == "FAIL"
    finding = next(f for f in report.findings if f.code == "ungrounded_row")
    assert finding.line == 2


def test_wrong_quantity_is_caught(clean_text):
    bad = make_po()
    bad.line_items[0] = LineItem(line=1, sku="AA-100", description="Widget small", serial="SN-1-A", qty=11, unit_price=Decimal("5.00"))
    assert verify(bad, clean_text).has("ungrounded_row")


def test_wrong_price_is_caught(clean_text):
    bad = make_po()
    bad.line_items[0] = LineItem(line=1, sku="AA-100", description="Widget small", serial="SN-1-A", qty=10, unit_price=Decimal("5.50"))
    assert verify(bad, clean_text).has("ungrounded_row")


def test_invented_header_value_is_caught(clean_text):
    report = verify(make_po(supplier="Totally Different Corp"), clean_text)
    assert report.status == "FAIL"
    assert report.has("ungrounded_field")


def test_invented_invoice_total_is_caught(clean_text):
    assert verify(make_po(invoice_total=Decimal("99.99")), clean_text).has("ungrounded_field")


def test_total_mismatch_fails_with_exact_difference():
    text = "PURCHASE ORDER #PO-1\nSupplier: Acme Parts Ltd Ship-to: Dallas DC-1. Terms.\n" \
           "1 AA-100 Widget small SN-1-A 10 $5.00\n2 BB-200 Widget large SN-1-B 2 $12.50\n" \
           "Invoice INV-9 for this PO totals $70.00 and is due.\n"
    report = verify(make_po(invoice_total=Decimal("70.00")), text)
    assert report.status == "FAIL"
    finding = next(f for f in report.findings if f.code == "invoice_total_mismatch")
    assert "$75.00" in finding.message and "$70.00" in finding.message and "$5.00" in finding.message


def test_missing_line_number_is_caught(clean_text):
    po = make_po()
    po.line_items[1] = LineItem(line=3, sku="BB-200", description="Widget large", serial="SN-1-B", qty=2, unit_price=Decimal("12.50"))
    assert verify(po, clean_text).has("line_numbers_not_contiguous")


def test_duplicate_serial_is_caught(clean_text):
    po = make_po()
    po.line_items[1] = LineItem(line=2, sku="BB-200", description="Widget large", serial="SN-1-A", qty=2, unit_price=Decimal("12.50"))
    assert verify(po, clean_text).has("duplicate_serial")


def test_no_line_items_fails(clean_text):
    assert verify(make_po(line_items=[]), clean_text).has("no_line_items")


def test_missing_invoice_total_is_a_warning_not_a_pass(clean_text):
    report = verify(make_po(invoice_total=None), clean_text)
    assert report.status == "REVIEW"
    assert report.has("invoice_total_missing")


def test_risk_note_is_linked_to_its_line_item(clean_text):
    text = clean_text + "Note: Item BB-200 was flagged during receiving and needs sign-off.\n"
    report = verify(make_po(), text)
    flagged = next(f for f in report.findings if f.code == "item_flagged")
    assert flagged.line == 2
    assert report.status == "REVIEW"


def test_money_uses_decimal_not_float():
    po = make_po()
    assert po.lines_total == Decimal("75.00")
    assert isinstance(po.lines_total, Decimal)
