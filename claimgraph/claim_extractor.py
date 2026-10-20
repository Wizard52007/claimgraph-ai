import json
import re
from pathlib import Path

from claimgraph.gemini_client import generate_text
from claimgraph.models import Claim


def extract_claims(pages: list[dict], document_name: str) -> list[Claim]:
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
    """Extract factual claims using Gemini and verify their source evidence."""
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
You are a careful research analyst extracting factual claims from a document.

Extract the distinct, meaningful, verifiable claims from the page below.

Rules:
1. Extract claims that could be checked against other evidence.
2. Preserve important numbers, dates, units, and qualifications.
3. Do not invent facts or add information absent from the source.
4. Do not extract headings, decorative text, or unsupported speculation as facts.
5. For every claim, provide evidence_text copied EXACTLY from the source.
6. evidence_text must be a contiguous substring of the source text.
7. A claim may summarize the evidence, but it must not change its meaning.
8. If there are no meaningful factual claims, return an empty array.
9. Return ONLY a valid JSON array. Do not use Markdown code fences.

Required JSON format:
[
  {{
    "text": "A concise factual claim",
    "evidence_text": "Exact supporting text from the source"
  }}
]

Source document: {document_name}
Page number: {page_number}

SOURCE TEXT:
{page_text}
"""

        response_text = generate_text(prompt)

        try:
            extracted = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Gemini returned invalid JSON for page {page_number}."
            ) from exc

        if not isinstance(extracted, list):
            raise ValueError(
                f"Gemini must return a JSON array for page {page_number}."
            )

        for item in extracted:
            if not isinstance(item, dict):
                raise ValueError("Each extracted claim must be a JSON object.")

            text = item.get("text")
            evidence_text = item.get("evidence_text")

            if not isinstance(text, str) or not text.strip():
                raise ValueError("Gemini returned a claim with empty text.")

            if not isinstance(evidence_text, str) or not evidence_text.strip():
                raise ValueError("Gemini returned empty supporting evidence.")

            if evidence_text not in page_text:
                raise ValueError(
                    f"Claim evidence could not be verified on page {page_number}."
                )

            claim = Claim(
                claim_id=f"{document_id}_claim_{claim_counter:03d}",
                text=text.strip(),
                document_name=document_name,
                page_number=page_number,
                evidence_text=evidence_text,
            )

            claims.append(claim)
            claim_counter += 1

    return claims