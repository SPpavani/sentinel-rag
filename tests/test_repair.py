import json

import pytest

from sentinel import process_text
from sentinel.llm import ExtractionError
from sentinel.repair import repair_stats

GOOD = {
    "po_number": "PO-1", "supplier": "Acme Parts Ltd", "ship_to": "Dallas DC-1",
    "invoice_number": "INV-9", "invoice_total": 75.0,
    "line_items": [
        {"line": 1, "sku": "AA-100", "description": "Widget small", "serial": "SN-1-A", "qty": 10, "unit_price": 5.0},
        {"line": 2, "sku": "BB-200", "description": "Widget large", "serial": "SN-1-B", "qty": 2, "unit_price": 12.5},
    ],
}


def variant(**changes):
    data = json.loads(json.dumps(GOOD))
    data.update(changes)
    return json.dumps(data)


def wrong_serial_line2():
    data = json.loads(json.dumps(GOOD))
    data["line_items"][1]["serial"] = "SN-1-Q"
    return json.dumps(data)


def wrong_serials_both():
    data = json.loads(json.dumps(GOOD))
    data["line_items"][0]["serial"] = "SN-1-X"
    data["line_items"][1]["serial"] = "SN-1-Q"
    return json.dumps(data)


def dropped_second_row():
    data = json.loads(json.dumps(GOOD))
    data["line_items"] = data["line_items"][:1]
    return json.dumps(data)


class Script:
    """A scripted model: returns the given replies in order (the last one repeats)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.replies[min(len(self.prompts) - 1, len(self.replies) - 1)]


def test_faithful_first_attempt_needs_no_repair(clean_text):
    model = Script(json.dumps(GOOD))
    result = process_text(clean_text, "llm", model)
    assert len(model.prompts) == 1
    assert result.report.status == "PASS"
    assert result.healed is False
    assert [a.status for a in result.attempts] == ["PASS"]


def test_model_fixes_its_own_hallucination_when_told_what_is_wrong(clean_text):
    model = Script(wrong_serial_line2(), json.dumps(GOOD))
    result = process_text(clean_text, "llm", model)
    assert [a.status for a in result.attempts] == ["FAIL", "PASS"]
    assert result.report.status == "PASS"
    assert result.healed is True


def test_repair_prompt_contains_exact_findings_and_previous_answer(clean_text):
    model = Script(wrong_serial_line2(), json.dumps(GOOD))
    process_text(clean_text, "llm", model)
    assert "these problems were found" not in model.prompts[0]
    second = model.prompts[1]
    assert "these problems were found" in second
    assert "line 2" in second and "SN-1-Q" in second          # finding + the model's previous answer
    assert "Never change a value to make totals match" in second


def test_loop_is_bounded_when_the_model_keeps_hallucinating(clean_text):
    model = Script(wrong_serial_line2())
    result = process_text(clean_text, "llm", model, max_attempts=3)
    assert len(model.prompts) == 3
    assert result.report.status == "FAIL"
    assert result.healed is False


def test_max_attempts_one_disables_repair(clean_text):
    model = Script(wrong_serial_line2(), json.dumps(GOOD))
    result = process_text(clean_text, "llm", model, max_attempts=1)
    assert len(model.prompts) == 1
    assert result.report.status == "FAIL"


def test_unparseable_reply_is_retried(clean_text):
    model = Script("Sorry, I can't do that.", json.dumps(GOOD))
    result = process_text(clean_text, "llm", model)
    assert [a.status for a in result.attempts] == ["UNPARSEABLE", "PASS"]
    assert result.healed is True
    assert "could not be used" in model.prompts[1]


def test_all_replies_unparseable_raises(clean_text):
    with pytest.raises(ExtractionError):
        process_text(clean_text, "llm", Script("nope"), max_attempts=2)


def test_returns_the_best_attempt_not_the_last(clean_text):
    model = Script(wrong_serial_line2(), wrong_serials_both())
    result = process_text(clean_text, "llm", model, max_attempts=3)
    assert [a.extraction_errors for a in result.attempts] == [1, 2, 2]
    assert result.po.line_items[0].serial == "SN-1-A"            # attempt 1 had only one wrong row
    assert len(result.report.by_severity("error")) == 1


def test_dropped_row_is_detected_and_repaired(clean_text):
    model = Script(dropped_second_row(), json.dumps(GOOD))
    result = process_text(clean_text, "llm", model)
    assert "row_count_mismatch" in result.attempts[0].error_codes
    assert "2 table rows but 1 were extracted" in model.prompts[1]
    assert result.report.status == "PASS" and result.healed is True


MISMATCH_TEXT = (
    "PURCHASE ORDER #PO-1\nSupplier: Acme Parts Ltd Ship-to: Dallas DC-1. Terms.\n"
    "1 AA-100 Widget small SN-1-A 10 $5.00\n2 BB-200 Widget large SN-1-B 2 $12.50\n"
    "Invoice INV-9 for this PO totals $70.00 and is due.\n"
)


def test_genuine_document_inconsistency_is_not_retried():
    model = Script(variant(invoice_total=70.0))
    result = process_text(MISMATCH_TEXT, "llm", model)
    assert len(model.prompts) == 1                      # nothing the model can fix by re-reading
    assert result.report.has("invoice_total_mismatch")
    assert result.report.status == "FAIL"
    assert result.healed is False


def test_mismatch_is_never_pushed_back_to_the_model():
    bad_then_good = Script(wrong_serial_line2(), variant(invoice_total=70.0))
    process_text(MISMATCH_TEXT, "llm", bad_then_good)
    assert "line items sum to" not in bad_then_good.prompts[1]


def test_fudging_a_total_to_force_a_match_is_still_caught():
    fudged = Script(variant(invoice_total=75.0))        # 75.00 is not in the document
    result = process_text(MISMATCH_TEXT, "llm", fudged)
    assert result.report.has("ungrounded_field")
    assert result.report.status == "FAIL"


def test_repair_stats(clean_text):
    runs = [
        process_text(clean_text, "llm", Script(json.dumps(GOOD))),                        # clean at once
        process_text(clean_text, "llm", Script(wrong_serial_line2(), json.dumps(GOOD))),  # healed
        process_text(clean_text, "llm", Script(wrong_serial_line2())),                    # never fixed
    ]
    stats = repair_stats(runs)
    assert stats == {"trials": 3, "first_attempt_clean": 1, "final_clean": 2, "healed": 1, "avg_attempts": 2.0}


def test_repair_stats_empty():
    assert repair_stats([])["trials"] == 0
