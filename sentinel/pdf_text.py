"""PDF -> text. Text is extracted page by page, then joined so tables that
split across a page break are still read as one continuous list of rows."""
from typing import List


def extract_pages(path: str) -> List[str]:
    import pdfplumber  # imported lazily

    with pdfplumber.open(path) as pdf:
        return [(page.extract_text() or "") for page in pdf.pages]


def join_pages(pages: List[str]) -> str:
    return "\n".join(pages)


def normalize(text: str) -> str:
    """Collapse all whitespace (including line breaks) to single spaces."""
    return " ".join(text.split())
