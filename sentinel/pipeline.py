"""End to end: PDF -> text -> extractor -> verification."""
from typing import Optional

from sentinel.llm import Completer, anthropic_completer, extract_with_llm
from sentinel.models import ProcessingResult
from sentinel.pdf_text import extract_pages, join_pages
from sentinel.rules import extract_po
from sentinel.verify import verify


def process_text(text: str, extractor: str = "rules", completer: Optional[Completer] = None) -> ProcessingResult:
    if extractor == "rules":
        po = extract_po(text)
    elif extractor == "llm":
        po = extract_with_llm(text, completer or anthropic_completer())
    else:
        raise ValueError("extractor must be 'rules' or 'llm'")
    return ProcessingResult(extractor=extractor, po=po, report=verify(po, text))


def process_pdf(path: str, extractor: str = "rules", completer: Optional[Completer] = None) -> ProcessingResult:
    return process_text(join_pages(extract_pages(path)), extractor, completer)
