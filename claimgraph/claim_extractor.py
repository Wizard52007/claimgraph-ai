import json
import re
from pathlib import Path

from claimgraph.gemini_client import generate_text
from claimgraph.models import Claim


def _normalize_text(text: str) -> str:
    """
    Normalize whitespace for evidence verification.

    This allows harmless differences in spaces and line breaks while
    preserving the actual words and punctuation.
    """
    return re.sub(r"\s+", " ", text).strip()


def _extract_json_array(response_text: str) -> list:
    """
    Parse a JSON array from the model response.

    Supports plain JSON and JSON wrapped in Markdown code fences.
    """
    response_text = response_text.strip()

    # First, try parsing the complete response.
    try:
        result = json.loads(response_text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Remove optional Markdown code fences.
    cleaned = re.sub(
        r"^\s*```(?:json)?\s*|\s*```\s*$",
        "",
        response_text,
        flags=re.IGNORECASE,
    ).strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try extracting a JSON array if the model added surrounding text.
    start = cleaned.find("[")
    end = cleaned.rfind("]")

    if start != -1 and end > start:
        try:
            result = json.loads(cleaned[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError("The AI model returned invalid JSON.")


def _verify_evidence(evidence_text: str, page_text: str) -> bool:
    """
    Verify that evidence is present in the original source text.

    First checks exact matching, then checks whitespace-normalized matching.
    It does not accept evidence that merely has a similar meaning.
    """
    if not evidence_text or not evidence_text.strip():
        return False

    if evidence_text in page_text:
        return True

    normalized_evidence = _normalize_text(evidence_text)
    normalized_page = _normalize_text(page_text)

    return normalized_evidence in normalized_page


def extract_claims(
    pages: list[dict],
    document_name: str,
) -> list[Claim]:
    """Extract sentence-level candidate claims from PDF pages."""
    claims = []
    claim_counter = 1

    document_id = re.sub(
        r"[^a-zA-Z0-9_]+",
        "_",
        Path(document_name).stem,
    ).strip("_").lower() or "document"

    for page in pages:
        page_number = page["page_number"]
        page_text = page["text"]

        sentences = re.split(r"(?<=[.!?])\s+", page_text.strip())

        for sentence in sentences:
            sentence = sentence.strip()

            if not sentence:
                continue

            claim = Claim(
                claim_id=f"{document_id}_claim_{claim_counter:03d}",
                text=sentence,
                document_name=document_name,
                page_number=page_number,
                evidence_text=sentence,
            )

            claims.append(claim)
            claim_counter += 1

    return claims


def extract_claims_with_gemini(
    pages: list[dict],
    document_name: str,
) -> list[Claim]:
    """
    Extract factual claims using the configured AI provider and verify
    that every claim has evidence in its original PDF page.
    """
    claims = []
    claim_counter = 1

    document_id = re.sub(
        r"[^a-zA-Z0-9_]+",
        "_",
        Path(document_name).stem,
    ).strip("_").lower() or "document"

    for page in pages:
        page_number = page["page_number"]
        page_text = page["text"]

        if not page_text.strip():
            continue

        prompt = f"""
You are a careful research analyst extracting factual claims from a PDF.

Extract distinct, meaningful, verifiable factual claims from the source page.

STRICT RULES:
1. Extract only claims supported by the provided source text.
2. Preserve numbers, dates, units, names, and qualifications.
3. Never invent facts or introduce outside knowledge.
4. Do not extract headings or decorative text as factual claims.
5. Every evidence_text MUST be copied directly from SOURCE TEXT.
6. Copy evidence_text verbatim. Do not paraphrase, rewrite, or correct it.
7. evidence_text must be one continuous passage from SOURCE TEXT.
8. Preserve the original words and punctuation in evidence_text.
9. The claim's text may summarize the evidence, but must preserve its meaning.
10. If no meaningful factual claims exist, return an empty array.
11. Return only a valid JSON array. No Markdown or explanations.

Required format:
[
  {{
    "text": "A concise factual claim",
    "evidence_text": "An exact passage copied from SOURCE TEXT"
  }}
]

Document: {document_name}
Page: {page_number}

SOURCE TEXT:
{page_text}
"""

        response_text = generate_text(prompt)
        extracted = _extract_json_array(response_text)

        for item in extracted:
            if not isinstance(item, dict):
                raise ValueError(
                    f"Each extracted claim must be a JSON object "
                    f"on page {page_number}."
                )

            text = item.get("text")
            evidence_text = item.get("evidence_text")

            if not isinstance(text, str) or not text.strip():
                raise ValueError(
                    f"The AI returned empty claim text on page {page_number}."
                )

            if (
                not isinstance(evidence_text, str)
                or not evidence_text.strip()
            ):
                raise ValueError(
                    f"The AI returned empty evidence on page {page_number}."
                )

            if not _verify_evidence(evidence_text, page_text):
               raise ValueError(
                  f"Claim evidence could not be verified on page "
                  f"{page_number} of {document_name}. "
                  "The AI may have paraphrased or invented the evidence."
              )

            claim = Claim(
                claim_id=f"{document_id}_claim_{claim_counter:03d}",
                text=text.strip(),
                document_name=document_name,
                page_number=page_number,
                evidence_text=evidence_text.strip(),
            )

            claims.append(claim)
            claim_counter += 1

    return claims