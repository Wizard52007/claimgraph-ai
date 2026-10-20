import pytest
from pydantic import ValidationError

from claimgraph.models import Claim


def test_valid_claim():
    claim = Claim(
        claim_id="claim_001",
        text="Solar capacity increased by 20%.",
        document_name="energy_report.pdf",
        page_number=3,
        evidence_text="Solar capacity increased by 20% in 2025.",
    )

    assert claim.claim_id == "claim_001"
    assert claim.page_number == 3


def test_empty_claim_text_is_rejected():
    with pytest.raises(ValidationError):
        Claim(
            claim_id="claim_002",
            text="",
            document_name="energy_report.pdf",
            page_number=1,
            evidence_text="Some evidence.",
        )


def test_invalid_page_number_is_rejected():
    with pytest.raises(ValidationError):
        Claim(
            claim_id="claim_003",
            text="A valid claim.",
            document_name="energy_report.pdf",
            page_number=0,
            evidence_text="Some evidence.",
        )