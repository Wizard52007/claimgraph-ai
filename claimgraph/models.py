from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """A claim extracted from a document."""

    claim_id: str
    text: str = Field(min_length=1)
    document_name: str
    page_number: int = Field(ge=1)
    evidence_text: str = Field(min_length=1)


class ClaimRelationship(BaseModel):
    """A classified relationship between two claims."""

    source_claim_id: str
    target_claim_id: str

    relation_type: Literal[
        "SUPPORTS",
        "CONTRADICTS",
        "QUALIFIES",
        "UNRELATED",
        "INSUFFICIENT_EVIDENCE",
    ]

    explanation: str = Field(min_length=1)

    source_evidence: str = Field(min_length=1)
    target_evidence: str = Field(min_length=1)