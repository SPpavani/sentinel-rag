"""LLM extractor for messy layouts, with a strict safety net.

The model's output is parsed and validated against the schema, and then the
Sentinel (verify.py) checks every value against the source document, so a
hallucinated serial number or price is caught instead of trusted.

The model call is injected as a plain function `complete(prompt) -> str`,
so the logic can be tested without any network or API key.
"""
import json
import os
from typing import Callable

from pydantic import ValidationError

from sentinel.models import PurchaseOrder

Completer = Callable[[str], str]


class ExtractionError(ValueError):
    """The model's reply could not be turned into a valid PurchaseOrder."""


PROMPT = """You extract data from a purchase order document. Copy values EXACTLY as written.
Never guess or calculate. Use null for anything that is not in the document.

Return ONLY a JSON object with this shape and nothing else:
{{
  "po_number": "string or null",
  "supplier": "string or null",
  "ship_to": "string or null",
  "invoice_number": "string or null",
  "invoice_total": number or null,
  "line_items": [
    {{"line": 1, "sku": "string", "description": "string", "serial": "string",
      "qty": 1, "unit_price": 0.00}}
  ]
}}

Include every line item, including rows that continue after a page break.

<document>
{document}
</document>"""


def build_prompt(document_text: str) -> str:
    return PROMPT.format(document=document_text)


def parse_llm_json(raw: str) -> dict:
    """Pull the JSON object out of a reply, tolerating ```json fences and chatter."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ExtractionError("the model reply contains no JSON object")
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"the model reply is not valid JSON: {exc}") from exc


def extract_with_llm(document_text: str, complete: Completer) -> PurchaseOrder:
    data = parse_llm_json(complete(build_prompt(document_text)))
    try:
        return PurchaseOrder.model_validate(data)
    except ValidationError as exc:
        raise ExtractionError(f"the extraction does not match the schema: {exc}") from exc


def anthropic_completer(model: str = "", max_tokens: int = 4096) -> Completer:
    """Build a `complete` function backed by the Anthropic API (needs ANTHROPIC_API_KEY)."""
    import anthropic  # lazy: optional dependency

    client = anthropic.Anthropic()
    chosen = model or os.getenv("SENTINEL_MODEL", "claude-haiku-4-5-20251001")

    def complete(prompt: str) -> str:
        response = client.messages.create(
            model=chosen,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")

    return complete
