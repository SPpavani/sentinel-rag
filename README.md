# Sentinel-RAG: verified extraction from procurement PDFs

[![CI](https://github.com/SPpavani/sentinel-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/SPpavani/sentinel-rag/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)

> **Never trust an AI (or a regex) with a serial number until it has been checked against the source document.**

In B2B supply chains, one wrong digit in a serial number, quantity or price can mean a wrong shipment, a failed audit or a duplicate payment. Language models are good at reading messy documents and also capable of silently inventing a plausible value. Sentinel puts a **deterministic verification layer** between any extractor and the downstream system.

```
PDF ─► text ─► extractor ─► Sentinel ─► PASS / REVIEW / FAIL + findings
               (rules OR LLM)   │
                                ├─ grounding     every value must exist in the source
                                ├─ completeness  line numbers 1..N, no duplicate serials
                                ├─ arithmetic    sum(qty x price) == invoice total, to the cent
                                └─ risk notes    flags, delays, tariffs, linked to the line item
```

## See it work (real output)

The bundled `sample_po.pdf` is a 3-page purchase order. Its 20-row table **splits across a page break**, the PDF hides a quality flag inside a paragraph, and the invoice total does not match the lines.

```bash
python -m sentinel sample_po.pdf
```

```
File:       sample_po.pdf   (extractor: rules)
PO number:  PO-88213
Supplier:   Meridian Fastener & Component Co.
Ship-to:    Austin DC-4
Line items: 20   sum: $15,253.40
Invoice:    INV-55021   total: $6,214.80

STATUS: FAIL

[ERROR  ] invoice_total_mismatch: line items sum to $15,253.40 but invoice INV-55021 states $6,214.80 (difference $9,038.60)
[WARNING] item_flagged (line 8): Note: Item HC-4474 (serial SN-88213-H8) was flagged during prior receiving for a documentation mismatch and requires manual QA sign-off before stocking.
[WARNING] risk_note: Of these, 3 shipments arrived after the agreed ETA, including a 9-day delay on PO-87550 attributed to a carrier customs hold at the Texas-Mexico border crossing.
[WARNING] risk_note: Region is currently under an active tariff advisory for imported alloy hardware.
```

The exit code is `0` for PASS, `1` for REVIEW and `2` for FAIL, so it can gate a pipeline.

### Catching a hallucinating model

`python examples/demo_hallucination.py` (no API key needed) simulates a model that reads the document correctly, then silently changes one serial number and one unit price:

```
Status: FAIL

[ERROR] line 5 (HC-4473, SN-88213-E7, qty 6, $201.75) does not match any row in the source
[ERROR] line 12 (MB-1093, SN-88213-L5, qty 24, $36.20) does not match any row in the source
```

Both errors are caught because each extracted row must exist as **one line of the source** containing all of its values.

## Quick start

```bash
git clone https://github.com/SPpavani/sentinel-rag.git
cd sentinel-rag
pip install -r requirements.txt

python -m sentinel sample_po.pdf                      # deterministic extractor
python -m sentinel sample_po.pdf --json result.json   # also save the full result

# LLM extractor for messy layouts (needs an API key)
pip install -r requirements-llm.txt
export ANTHROPIC_API_KEY="your-key"
python -m sentinel your_document.pdf --extractor llm
```

From Python:

```python
from sentinel import process_pdf

result = process_pdf("sample_po.pdf")
print(result.report.status)          # FAIL
for finding in result.report.findings:
    print(finding.severity, finding.code, finding.line)
```

## How the checks work

| Check | Rule | Catches |
|---|---|---|
| Grounding (header) | PO number, supplier, ship-to, invoice number and total must appear in the source text | Invented or altered header values |
| Grounding (rows) | Each line item must exist as a single source line containing its line number, SKU, serial, quantity, unit price and description | Wrong serials, quantities and prices; rows stitched together from different places |
| Completeness | Line numbers are exactly 1..N; no serial appears twice | Dropped or duplicated rows |
| Arithmetic | `sum(qty x unit price)` equals the invoice total exactly (Decimal, never float) | Mismatched invoices and dropped rows (when the total is present) |
| Risk notes | Sentences containing words like flagged, mismatch, sign-off, delay, customs hold, tariff advisory are surfaced and linked to the line item they mention | Warnings buried in prose |

Status: any error gives **FAIL**; warnings only give **REVIEW**; otherwise **PASS**.

## Two extractors, one verifier

| | `rules` (default) | `llm` |
|---|---|---|
| How | Regular expressions over the PDF text | Prompt a model, parse JSON, validate against the schema |
| Strength | Cannot hallucinate; free; instant | Handles layouts you have not seen |
| Weakness | Tied to one layout | Can invent values, which is why the verifier exists |
| Model call | none | injected as a plain function, so it is testable offline |

The verifier does not know or care which extractor produced the data.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q        # 30 tests, about 1 second, no network or API key
```

The suite covers every check, the LLM JSON parsing (fences, chatter, broken JSON, schema violations), a faithful LLM passing and a hallucinating LLM being caught, and end-to-end runs on the real sample PDF including the page-split table. CI runs on Python 3.10, 3.11 and 3.12.

## Design decisions

- **Verification is independent of extraction.** You can swap in a better model without touching the safety net.
- **Decimal money.** Float rounding must never decide whether an invoice reconciles.
- **Row-level grounding.** Checking that each value appears *somewhere* in the document is not enough; the whole row must co-occur on one line.
- **Tables are read from the joined text**, so rows split across a page break are not lost, and repeated header rows are ignored.
- **Offline-testable LLM path.** The model call is an injected function.

## Limitations

- The `rules` extractor is written for this purchase-order layout. New layouts need new rules or the LLM extractor.
- The LLM extractor is tested with simulated models only. Its accuracy with a real model on real documents has not been measured yet.
- Text-based PDFs only. Scanned documents need OCR first.
- One document type (purchase orders). Bills of lading, packing lists and certificates are not implemented.
- Risk notes are keyword-based, so they can miss a warning phrased in unexpected words.
- Verification catches wrong or invented values and inconsistent totals. It cannot know that a value is wrong if the source document itself is wrong in a consistent way.

## Roadmap

- [ ] OCR for scanned PDFs (Docling or Tesseract)
- [ ] More document types: bill of lading, packing list, supplier certificate
- [ ] Three-way match: purchase order vs invoice vs receiving record
- [ ] Field-level accuracy benchmark on a labelled set of documents, rules vs LLM
- [ ] Review queue: route REVIEW and FAIL documents to a human with the exact evidence
- [ ] FastAPI service and an MCP tool so other systems and AI assistants can call it

## Repo layout

```
sentinel/
  models.py     typed data models (Pydantic, Decimal money)
  pdf_text.py   PDF to text, page by page
  rules.py      deterministic extractor
  llm.py        LLM extractor with injected model call
  verify.py     the Sentinel: grounding, completeness, arithmetic
  risk.py       risk notes linked to line items
  pipeline.py   PDF to text to extractor to verification
  __main__.py   command line (python -m sentinel)
scripts/make_sample_po.py   regenerates the sample PDF
examples/                   demo and sample output
tests/                      30 tests
```
