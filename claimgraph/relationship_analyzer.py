import json

from claimgraph.gemini_client import generate_text
from claimgraph.models import Claim, ClaimRelationship


VALID_RELATIONSHIPS = {
    "SUPPORTS",
    "CONTRADICTS",
    "QUALIFIES",
    "UNRELATED",
    "INSUFFICIENT_EVIDENCE",
}


def analyze_relationship(
    source_claim: Claim,
    target_claim: Claim,
) -> ClaimRelationship:
    """Analyze the relationship between two claims using Gemini."""

    if source_claim.claim_id == target_claim.claim_id:
        raise ValueError("Cannot compare a claim with itself.")

    prompt = f"""
You are an evidence analyst comparing two factual claims.

Determine the relationship of Claim A to Claim B.

Choose exactly one category:

SUPPORTS:
Claim A provides evidence consistent with Claim B.

CONTRADICTS:
Claim A conflicts with Claim B on a relevant fact.
Only use this when the claims concern sufficiently comparable facts.

QUALIFIES:
Claim A adds context, a limitation, or a qualification that changes
how Claim B should be interpreted.

UNRELATED:
The claims do not have a meaningful evidential relationship.

INSUFFICIENT_EVIDENCE:
The available information is insufficient to classify the relationship
reliably.

Important rules:
1. Do not assume that similar wording means the claims support each other.
2. Check relevant dates, geographic scope, units, and definitions.
3. Do not invent facts or use knowledge absent from the supplied claims.
4. If the relationship is ambiguous, choose INSUFFICIENT_EVIDENCE.
5. Return ONLY a valid JSON object, without Markdown code fences.
6. The explanation must briefly justify your classification.

Required format:
{{
    "relation_type": "SUPPORTS",
    "explanation": "Brief explanation of the relationship."
}}

CLAIM A:
{source_claim.text}

CLAIM A SOURCE:
{source_claim.document_name}, page {source_claim.page_number}
Evidence: {source_claim.evidence_text}

CLAIM B:
{target_claim.text}

CLAIM B SOURCE:
{target_claim.document_name}, page {target_claim.page_number}
Evidence: {target_claim.evidence_text}
"""

    response_text = generate_text(prompt)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON for the relationship."
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("Gemini must return a JSON object.")

    relation_type = result.get("relation_type")
    explanation = result.get("explanation")

    if relation_type not in VALID_RELATIONSHIPS:
        raise ValueError(
            f"Invalid relationship category: {relation_type!r}"
        )

    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Gemini returned an empty explanation.")

    return ClaimRelationship(
        source_claim_id=source_claim.claim_id,
        target_claim_id=target_claim.claim_id,
        relation_type=relation_type,
        explanation=explanation.strip(),
        source_evidence=source_claim.evidence_text,
        target_evidence=target_claim.evidence_text,
    )