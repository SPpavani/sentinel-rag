from decimal import Decimal

from sentinel.models import LineItem
from sentinel.verify import verify

from conftest import make_po


def test_dropped_row_is_flagged(clean_text):
    po = make_po()
    po.line_items = po.line_items[:1]
    report = verify(po, clean_text)
    finding = next(f for f in report.findings if f.code == "row_count_mismatch")
    assert "2 table rows but 1 were extracted" in finding.message


def test_matching_row_count_is_not_flagged(clean_text):
    assert not verify(make_po(), clean_text).has("row_count_mismatch")


def test_no_row_like_lines_in_source_means_no_row_count_check():
    po = make_po(line_items=[LineItem(line=1, sku="AA-100", description="x", serial="SN-1-A", qty=1, unit_price=Decimal("1.00"))])
    assert not verify(po, "free text with no table at all").has("row_count_mismatch")


def test_empty_extraction_reports_no_line_items_only(clean_text):
    report = verify(make_po(line_items=[]), clean_text)
    assert report.has("no_line_items") and not report.has("row_count_mismatch")
