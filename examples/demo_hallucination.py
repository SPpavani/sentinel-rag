"""Demo (no API key needed): a simulated LLM that makes two realistic mistakes.

The 'model' reads the document correctly, then silently changes one serial number
and one unit price, which is the kind of error that is hard to spot by eye.
Sentinel checks every value against the source and catches both.

Run:  python examples/demo_hallucination.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel import process_text
from sentinel.pdf_text import extract_pages, join_pages
from sentinel.rules import extract_po

PDF = Path(__file__).resolve().parent.parent / "sample_po.pdf"


def fake_llm(prompt: str) -> str:
    text = prompt.split("<document>")[1].split("</document>")[0]
    data = json.loads(extract_po(text).model_dump_json())
    data["line_items"][4]["serial"] = "SN-88213-E7"     # real value: SN-88213-E2
    data["line_items"][11]["unit_price"] = "36.20"       # real value: 38.20
    return json.dumps(data)


text = join_pages(extract_pages(str(PDF)))
result = process_text(text, extractor="llm", completer=fake_llm)

print(f"Status: {result.report.status}\n")
for f in result.report.findings:
    if f.code == "ungrounded_row":
        print(f"[{f.severity.upper()}] {f.message}")
