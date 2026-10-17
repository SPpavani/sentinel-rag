"""End to end: PDF -> text -> extractor -> verification (-> self-correction for the LLM)."""
from typing import Optional

from sentinel.llm import Completer, anthropic_completer
from sentinel.models import ProcessingResult
from sentinel.pdf_text import extract_pages, join_pages
from sentinel.repair import extract_with_repair
from sentinel.rules import extract_po
from sentinel.verify import extraction_errors, verify


def process_text(
    text: str,
    extractor: str = "rules",
    completer: Optional[Completer] = None,
    max_attempts: int = 3,
) -> ProcessingResult:
    """max_attempts applies to the LLM extractor: 1 = no self-correction."""
    if extractor == "rules":
        po = extract_po(text)
        return ProcessingResult(extractor=extractor, po=po, report=verify(po, text))
    if extractor == "llm":
        po, report, attempts = extract_with_repair(text, completer or anthropic_completer(), max_attempts)
        healed = attempts[0].extraction_errors > 0 and not extraction_errors(report)
        return ProcessingResult(extractor=extractor, po=po, report=report, attempts=attempts, healed=healed)
    raise ValueError("extractor must be 'rules' or 'llm'")


def process_pdf(
    path: str,
    extractor: str = "rules",
    completer: Optional[Completer] = None,
    max_attempts: int = 3,
) -> ProcessingResult:
    return process_text(join_pages(extract_pages(path)), extractor, completer, max_attempts)
