"""Self-correcting extraction.

  ask the model -> verify against the source -> if the verifier found errors the
  model can fix, send those exact findings back and ask again -> verify again ...

The model is never trusted: every attempt is re-verified from scratch, so a
"repair" that changes a value to something not in the document is caught like
any other hallucination. The loop is bounded, and it returns the BEST attempt
(fewest fixable errors), never a worse later one.

What is not retried: genuine inconsistencies in the document itself (e.g. an
invoice total that disagrees with the lines). The model cannot fix those by
re-reading, and asking it to would invite it to fudge numbers.
"""
from typing import List, Optional, Tuple

from sentinel.llm import Completer, ExtractionError, build_prompt, po_from_reply
from sentinel.models import Attempt, PurchaseOrder, VerificationReport
from sentinel.verify import extraction_errors, verify

REPAIR_INSTRUCTIONS = """Your previous answer was checked against the document and these problems were found:
{problems}

Re-read the document carefully and return a corrected JSON object with the same shape.
Rules:
- Copy values EXACTLY as written in the document.
- Fix only what is wrong; keep everything that was correct.
- Include every table row, including rows that continue after a page break.
- Never change a value to make totals match. If the document states it, keep it.
- Use null for anything that is not in the document.
Return ONLY the JSON object."""


def build_repair_prompt(document_text: str, previous_reply: str, problems: List[str]) -> str:
    bullets = "\n".join(f"- {p}" for p in problems)
    return (
        build_prompt(document_text)
        + "\n\nYour previous answer:\n"
        + previous_reply.strip()
        + "\n\n"
        + REPAIR_INSTRUCTIONS.format(problems=bullets)
    )


def extract_with_repair(
    document_text: str,
    complete: Completer,
    max_attempts: int = 3,
) -> Tuple[PurchaseOrder, VerificationReport, List[Attempt]]:
    """Returns (best extraction, its verification report, history of attempts)."""
    attempts: List[Attempt] = []
    best: Optional[Tuple[PurchaseOrder, VerificationReport, int]] = None
    last_error = ""
    prompt = build_prompt(document_text)

    for number in range(1, max(1, max_attempts) + 1):
        raw = complete(prompt)
        try:
            po = po_from_reply(raw)
        except ExtractionError as exc:
            last_error = str(exc)
            attempts.append(Attempt(number=number, status="UNPARSEABLE", error_count=1,
                                    extraction_errors=1, error_codes=["unparseable_reply"], detail=last_error))
            prompt = build_repair_prompt(document_text, raw, [f"Your reply could not be used: {last_error}"])
            continue

        report = verify(po, document_text)
        fixable = extraction_errors(report)
        errors = report.by_severity("error")
        attempts.append(Attempt(
            number=number,
            status=report.status,
            error_count=len(errors),
            extraction_errors=len(fixable),
            error_codes=sorted({f.code for f in errors}),
        ))
        if best is None or len(fixable) <= best[2]:     # latest wins ties
            best = (po, report, len(fixable))
        if not fixable:
            break
        prompt = build_repair_prompt(document_text, raw, [f.message for f in fixable])

    if best is None:
        raise ExtractionError(f"no usable extraction after {len(attempts)} attempt(s): {last_error}")
    return best[0], best[1], attempts


def repair_stats(results) -> dict:
    """Summarise many runs: how often is the first attempt clean, how often does the loop fix it?

    'clean' means no extraction errors (document-level findings such as an invoice
    mismatch are not the model's fault and are ignored here).
    """
    n = len(results)
    if not n:
        return {"trials": 0, "first_attempt_clean": 0, "final_clean": 0, "healed": 0, "avg_attempts": 0.0}
    return {
        "trials": n,
        "first_attempt_clean": sum(1 for r in results if r.attempts and r.attempts[0].extraction_errors == 0),
        "final_clean": sum(1 for r in results if not extraction_errors(r.report)),
        "healed": sum(1 for r in results if r.healed),
        "avg_attempts": round(sum(len(r.attempts) for r in results) / n, 2),
    }
