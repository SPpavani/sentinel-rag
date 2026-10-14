import json

import pytest

from sentinel import process_text
from sentinel.llm import ExtractionError, extract_with_llm, parse_llm_json

GOOD = {
    "po_number": "PO-1", "supplier": "Acme Parts Ltd", "ship_to": "Dallas DC-1",
    "invoice_number": "INV-9", "invoice_total": 75.0,
    "line_items": [
        {"line": 1, "sku": "AA-100", "description": "Widget small", "serial": "SN-1-A", "qty": 10, "unit_price": 5.0},
        {"line": 2, "sku": "BB-200", "description": "Widget large", "serial": "SN-1-B", "qty": 2, "unit_price": 12.5},
    ],
}


def test_parse_plain_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_parse_json_inside_markdown_fence_and_chatter():
    assert parse_llm_json('Sure!\n```json\n{"a": 1}\n```\nHope that helps') == {"a": 1}


def test_parse_rejects_reply_without_json():
    with pytest.raises(ExtractionError):
        parse_llm_json("I could not read the document")


def test_parse_rejects_broken_json():
    with pytest.raises(ExtractionError):
        parse_llm_json('{"a": }')


def test_schema_violation_raises():
    bad = dict(GOOD, line_items=[{"line": 1, "sku": "AA-100"}])
    with pytest.raises(ExtractionError):
        extract_with_llm("doc", lambda prompt: json.dumps(bad))


def test_prompt_contains_the_document():
    seen = []
    extract_with_llm("MY DOCUMENT TEXT", lambda prompt: seen.append(prompt) or json.dumps(GOOD))
    assert "MY DOCUMENT TEXT" in seen[0]


def test_faithful_llm_extraction_passes_verification(clean_text):
    result = process_text(clean_text, extractor="llm", completer=lambda p: json.dumps(GOOD))
    assert result.extractor == "llm"
    assert result.report.status == "PASS"


def test_hallucinating_llm_is_caught_by_the_sentinel(clean_text):
    hallucinated = json.loads(json.dumps(GOOD))
    hallucinated["line_items"][1]["serial"] = "SN-1-Q"       # invented serial
    hallucinated["line_items"][0]["unit_price"] = 6.0         # invented price
    result = process_text(clean_text, extractor="llm", completer=lambda p: json.dumps(hallucinated))
    assert result.report.status == "FAIL"
    bad_lines = {f.line for f in result.report.findings if f.code == "ungrounded_row"}
    assert bad_lines == {1, 2}


def test_unknown_extractor_is_rejected(clean_text):
    with pytest.raises(ValueError):
        process_text(clean_text, extractor="magic")
