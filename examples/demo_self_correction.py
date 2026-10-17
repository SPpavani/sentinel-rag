"""Demo (no API key needed): the self-correcting loop on the real sample PO.

A SIMULATED model makes three realistic mistakes on its first try:
  - changes a serial number (line 5)
  - changes a unit price (line 12)
  - drops the last table row (line 20)
Sentinel finds all three and sends the exact findings back. The model here is a
scripted stand-in that re-reads correctly once told what is wrong; with a real
model, use `python -m sentinel file.pdf --extractor llm` or scripts/measure_repair.py.

Run:  python examples/demo_self_correction.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel import process_text
from sentinel.pdf_text import extract_pages, join_pages
from sentinel.rules import extract_po

PDF = Path(__file__).resolve().parent.parent / "sample_po.pdf"
TEXT = join_pages(extract_pages(str(PDF)))
TRUTH = json.loads(extract_po(TEXT).model_dump_json())          # what a perfect reader would return


def simulated_model(prompt: str) -> str:
    """Attempt 1: three mistakes. After it is told what is wrong: a correct re-read."""
    data = json.loads(json.dumps(TRUTH))
    if "these problems were found" in prompt:
        return json.dumps(data)
    data["line_items"][4]["serial"] = "SN-88213-E7"       # real value: SN-88213-E2
    data["line_items"][11]["unit_price"] = "36.20"         # real value: 38.20
    data["line_items"] = data["line_items"][:-1]           # drops line 20
    return json.dumps(data)


result = process_text(TEXT, extractor="llm", completer=simulated_model, max_attempts=3)

print("Attempts:")
for a in result.attempts:
    print(f"  {a.number}: {a.status:5}  extraction errors: {a.extraction_errors}  {a.error_codes}")
print(f"\nSelf-corrected: {result.healed}")
remaining = [f for f in result.report.findings if f.severity == "error"]
print(f"Errors left: {len(remaining)}")
for f in remaining:
    print(f"  [{f.code}] {f.message}")
print("\n(The invoice mismatch is a real inconsistency in the document, so it is reported, not 'fixed'.)")
