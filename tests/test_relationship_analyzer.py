import json

import pytest

from claimgraph.models import Claim
from claimgraph.relationship_analyzer import analyze_relationship


@pytest.fixture
def source_claim():
    return Claim(
        claim_id="report_a_claim_001",
        text="India's solar capacity reached 100 GW in 2025.",
        document_name="report_a.pdf",
        page_number=2,
        evidence_text="India's solar capacity reached 100 GW in 2025.",
    )


@pytest.fixture
def target_claim():
    return Claim(
        claim_id="report_b_claim_001",
        text="India's solar capacity reached 80 GW in 2025.",
        document_name="report_b.pdf",
        page_number=4,
        evidence_text="India's solar capacity reached 80 GW in 2025.",
    )


def test_contradictory_claims_are_classified(monkeypatch, source_claim, target_claim):
    simulated_response = {
        "relation_type": "CONTRADICTS",
        "explanation": "The claims report different capacity figures.",
    }

    monkeypatch.setattr(
        "claimgraph.relationship_analyzer.generate_text",
        lambda prompt: json.dumps(simulated_response),
    )

    relationship = analyze_relationship(source_claim, target_claim)

    assert relationship.relation_type == "CONTRADICTS"
    assert relationship.source_claim_id == source_claim.claim_id
    assert relationship.target_claim_id == target_claim.claim_id


def test_original_evidence_is_preserved(monkeypatch, source_claim, target_claim):
    simulated_response = {
        "relation_type": "CONTRADICTS",
        "explanation": "The figures differ.",
    }

    monkeypatch.setattr(
        "claimgraph.relationship_analyzer.generate_text",
        lambda prompt: json.dumps(simulated_response),
    )

    relationship = analyze_relationship(source_claim, target_claim)

    assert relationship.source_evidence == source_claim.evidence_text
    assert relationship.target_evidence == target_claim.evidence_text


def test_invalid_relationship_category_is_rejected(
    monkeypatch, source_claim, target_claim
):
    simulated_response = {
        "relation_type": "MAYBE",
        "explanation": "Uncertain relationship.",
    }

    monkeypatch.setattr(
        "claimgraph.relationship_analyzer.generate_text",
        lambda prompt: json.dumps(simulated_response),
    )

    with pytest.raises(ValueError, match="Invalid relationship category"):
        analyze_relationship(source_claim, target_claim)


def test_invalid_json_is_rejected(monkeypatch, source_claim, target_claim):
    monkeypatch.setattr(
        "claimgraph.relationship_analyzer.generate_text",
        lambda prompt: "This is not JSON",
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        analyze_relationship(source_claim, target_claim)


def test_claim_cannot_be_compared_with_itself(monkeypatch, source_claim):
    with pytest.raises(ValueError, match="Cannot compare a claim with itself"):
        analyze_relationship(source_claim, source_claim)