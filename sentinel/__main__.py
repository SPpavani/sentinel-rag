"""Command line: python -m sentinel <file.pdf> [--extractor rules|llm] [--json out.json]

Exit code: 0 = PASS, 1 = REVIEW (warnings), 2 = FAIL (errors). CI-friendly.
"""
import argparse
import json
import sys

from sentinel.pipeline import process_pdf

ORDER = {"error": 0, "warning": 1, "info": 2}
EXIT = {"PASS": 0, "REVIEW": 1, "FAIL": 2}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel", description=__doc__)
    parser.add_argument("pdf")
    parser.add_argument("--extractor", choices=["rules", "llm"], default="rules")
    parser.add_argument("--max-attempts", type=int, default=3,
                        help="LLM extractor only: rounds of self-correction (1 = off, default 3)")
    parser.add_argument("--json", metavar="FILE", help="also write the full result as JSON")
    args = parser.parse_args(argv)

    result = process_pdf(args.pdf, extractor=args.extractor, max_attempts=args.max_attempts)
    po, report = result.po, result.report

    print(f"File:       {args.pdf}   (extractor: {result.extractor})")
    print(f"PO number:  {po.po_number}")
    print(f"Supplier:   {po.supplier}")
    print(f"Ship-to:    {po.ship_to}")
    print(f"Line items: {len(po.line_items)}   sum: ${po.lines_total:,.2f}")
    if po.invoice_total is not None:
        print(f"Invoice:    {po.invoice_number}   total: ${po.invoice_total:,.2f}")
    if result.attempts:
        print("\nAttempts:")
        for a in result.attempts:
            codes = f" ({', '.join(a.error_codes)})" if a.error_codes else ""
            print(f"  {a.number}: {a.status}{codes}")
        if result.healed:
            print("  -> self-corrected: the model fixed its own extraction errors")
    print(f"\nSTATUS: {report.status}\n")
    for f in sorted(report.findings, key=lambda f: ORDER[f.severity]):
        where = f" (line {f.line})" if f.line else ""
        print(f"[{f.severity.upper():7}] {f.code}{where}: {f.message}")

    if args.json:
        payload = result.model_dump(mode="json")
        payload["lines_total"] = str(po.lines_total)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    return EXIT[report.status]


if __name__ == "__main__":
    sys.exit(main())
