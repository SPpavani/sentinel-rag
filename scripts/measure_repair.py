"""Measure the self-correcting loop with a REAL model (needs ANTHROPIC_API_KEY).

Runs the LLM extractor several times on a PDF and reports how often the first
attempt is clean versus how often the loop ends clean. 'Clean' means no
extraction errors; document-level findings (e.g. an invoice mismatch in the
document itself) are not the model's fault and are ignored.

Usage:
    pip install -r requirements-llm.txt
    export ANTHROPIC_API_KEY="your-key"
    python scripts/measure_repair.py [--pdf sample_po.pdf] [--trials 10] [--max-attempts 3]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel import process_pdf
from sentinel.llm import anthropic_completer
from sentinel.repair import repair_stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", default="sample_po.pdf")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()

    completer = anthropic_completer()
    results = []
    for i in range(1, args.trials + 1):
        result = process_pdf(args.pdf, extractor="llm", completer=completer, max_attempts=args.max_attempts)
        results.append(result)
        trail = " -> ".join(f"{a.status}({a.extraction_errors})" for a in result.attempts)
        print(f"trial {i:>2}: {trail}")

    s = repair_stats(results)
    n = s["trials"]
    print(f"\nTrials: {n}   max attempts: {args.max_attempts}")
    print(f"Clean on the first attempt: {s['first_attempt_clean']}/{n}")
    print(f"Clean after self-correction: {s['final_clean']}/{n}   (fixed by the loop: {s['healed']})")
    print(f"Average attempts per document: {s['avg_attempts']}")


if __name__ == "__main__":
    main()
