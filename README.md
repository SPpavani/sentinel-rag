# Sentinel-RAG: Enterprise Agentic RAG Blueprint

**Domain:** B2B supply chain procurement & logistics
**Goal:** near-zero-error extraction from messy, multi-page PDFs: purchase orders (POs), bills of lading (BOLs), invoices, packing lists and supplier certificates. These contain serial numbers, tabular pricing and compliance data, where a single wrong digit matters.

> **Status: design blueprint with early loader prototypes.** The architecture below is the target. The scripts in this repo cover the first step, document loading.

## Why plain RAG is not enough here

Standard chunk-and-embed RAG breaks on procurement documents:

- Tables get split mid-row, so prices end up detached from part numbers
- Serial numbers and part codes are exact strings that embeddings blur
- Compliance answers must be traceable to a page and a source document

## Target architecture

```
PDFs ──► table-aware parsing ──► structured fields (schema-validated)
                                         │
              ┌──────────────────────────┴───────────────┐
              ▼                                          ▼
   exact-match store (serials, PO numbers)     vector store (descriptions, clauses)
              └──────────────────────────┬───────────────┘
                                         ▼
                      agent: route question → retrieve → verify against source
                                         ▼
                              answer + page-level citation
```

## What exists today

| File | Purpose |
|---|---|
| `loading pdf.py` | Loads a PDF page by page with `PyPDFLoader` (one document per page, with source and page metadata) |
| `recursive crawl.py` | Crawls a documentation site with `RecursiveUrlLoader` and strips nav/footer/script tags |
| `Make test pdf · PY` | Script for generating test documents |
| `sample_po.pdf` | Sample purchase order for testing |

## Roadmap

- [ ] Table-aware PDF parsing
- [ ] Pydantic schema extraction with validation (PO number, line items, totals)
- [ ] Exact-match lookup for serial numbers alongside vector search
- [ ] Verification step: every extracted value checked against its source page
- [ ] Evaluation set with field-level accuracy
- [ ] Rename scripts to snake_case and move them into `src/`
