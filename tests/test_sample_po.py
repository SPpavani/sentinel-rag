"""End-to-end tests on the real bundled PDF (a 3-page PO whose table splits across pages)."""
import json
from decimal import Decimal

from sentinel import process_pdf
from sentinel.__main__ import main
from sentinel.pdf_text import extract_pages


def test_pdf_has_three_pages(sample_pdf):
    assert len(extract_pages(sample_pdf)) == 3


def test_header_fields_are_extracted(sample_pdf):
    po = process_pdf(sample_pdf).po
    assert po.po_number == "PO-88213"
    assert po.supplier == "Meridian Fastener & Component Co."
    assert po.ship_to == "Austin DC-4"
    assert po.invoice_number == "INV-55021"
    assert po.invoice_total == Decimal("6214.80")


def test_table_split_across_pages_is_read_completely(sample_pdf):
    po = process_pdf(sample_pdf).po
    assert [i.line for i in po.line_items] == list(range(1, 21))   # rows 1-9 on page 1, 10-20 on page 2
    first, last = po.line_items[0], po.line_items[-1]
    assert (first.sku, first.serial, first.qty, first.unit_price) == ("HC-4471", "SN-88213-A7", 12, Decimal("142.50"))
    assert (last.sku, last.serial, last.qty, last.unit_price) == ("VL-1802", "SN-88213-T0", 10, Decimal("96.20"))


def test_all_extracted_rows_are_grounded(sample_pdf):
    report = process_pdf(sample_pdf).report
    assert not report.has("ungrounded_row")
    assert not report.has("ungrounded_field")


def test_invoice_total_does_not_match_the_line_items(sample_pdf):
    result = process_pdf(sample_pdf)
    assert result.po.lines_total == Decimal("15253.40")
    finding = next(f for f in result.report.findings if f.code == "invoice_total_mismatch")
    assert "$15,253.40" in finding.message and "$6,214.80" in finding.message and "$9,038.60" in finding.message
    assert result.report.status == "FAIL"


def test_flagged_item_is_linked_to_line_8(sample_pdf):
    findings = process_pdf(sample_pdf).report.findings
    flagged = [f for f in findings if f.code == "item_flagged"]
    assert len(flagged) == 1 and flagged[0].line == 8
    assert "HC-4474" in flagged[0].message


def test_supplier_risk_notes_are_surfaced(sample_pdf):
    messages = " ".join(f.message for f in process_pdf(sample_pdf).report.findings if f.code == "risk_note")
    assert "customs hold" in messages
    assert "tariff advisory" in messages


def test_cli_exit_code_and_json_output(sample_pdf, tmp_path, capsys):
    out = tmp_path / "result.json"
    code = main([sample_pdf, "--json", str(out)])
    assert code == 2                      # FAIL
    assert "STATUS: FAIL" in capsys.readouterr().out
    data = json.loads(out.read_text())
    assert data["report"]["status"] == "FAIL"
    assert data["lines_total"] == "15253.40"
