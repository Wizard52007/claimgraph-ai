from claimgraph.comparison_pipeline import compare_claims
from claimgraph.models import Claim, ClaimRelationship


def make_claim(
    claim_id: str,
    document_name: str,
    text: str,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=text,
        document_name=document_name,
        page_number=1,
        evidence_text=text,
    )


def test_compares_claims_from_different_documents(monkeypatch):
    claims = [
        make_claim("a1", "report_a.pdf", "Solar capacity reached 100 GW."),
        make_claim("b1", "report_b.pdf", "Solar capacity reached 100 GW."),
    ]

    def fake_analyzer(claim_a, claim_b):
        return ClaimRelationship(
            source_claim_id=claim_a.claim_id,
            target_claim_id=claim_b.claim_id,
            relation_type="SUPPORTS",
            explanation="The claims report the same figure.",
            source_evidence=claim_a.evidence_text,
            target_evidence=claim_b.evidence_text,
        )

    monkeypatch.setattr(
        "claimgraph.comparison_pipeline.analyze_relationship",
        fake_analyzer,
    )

    relationships = compare_claims(claims)

    assert len(relationships) == 1
    assert relationships[0].source_claim_id == "a1"
    assert relationships[0].target_claim_id == "b1"


def test_skips_claims_from_the_same_document(monkeypatch):
    claims = [
        make_claim("a1", "report_a.pdf", "Solar capacity increased."),
        make_claim("a2", "report_a.pdf", "Wind capacity increased."),
    ]

    def unexpected_analyzer(*args):
        raise AssertionError("Same-document claims should be skipped.")

    monkeypatch.setattr(
        "claimgraph.comparison_pipeline.analyze_relationship",
        unexpected_analyzer,
    )

    relationships = compare_claims(claims)

    assert relationships == []


def test_compares_all_eligible_pairs(monkeypatch):
    claims = [
        make_claim("a1", "report_a.pdf", "Claim A."),
        make_claim("b1", "report_b.pdf", "Claim B."),
        make_claim("c1", "report_c.pdf", "Claim C."),
    ]

    def fake_analyzer(claim_a, claim_b):
        return ClaimRelationship(
            source_claim_id=claim_a.claim_id,
            target_claim_id=claim_b.claim_id,
            relation_type="UNRELATED",
            explanation="No meaningful relationship was found.",
            source_evidence=claim_a.evidence_text,
            target_evidence=claim_b.evidence_text,
        )

    monkeypatch.setattr(
        "claimgraph.comparison_pipeline.analyze_relationship",
        fake_analyzer,
    )

    relationships = compare_claims(claims)

    assert len(relationships) == 3


def test_empty_claim_list_returns_no_relationships():
    assert compare_claims([]) == []


def test_same_document_comparison_can_be_enabled(monkeypatch):
    claims = [
        make_claim("a1", "report_a.pdf", "Solar capacity increased."),
        make_claim("a2", "report_a.pdf", "Wind capacity increased."),
    ]

    def fake_analyzer(claim_a, claim_b):
        return ClaimRelationship(
            source_claim_id=claim_a.claim_id,
            target_claim_id=claim_b.claim_id,
            relation_type="UNRELATED",
            explanation="The claims concern different energy sources.",
            source_evidence=claim_a.evidence_text,
            target_evidence=claim_b.evidence_text,
        )

    monkeypatch.setattr(
        "claimgraph.comparison_pipeline.analyze_relationship",
        fake_analyzer,
    )

    relationships = compare_claims(
        claims,
        cross_document_only=False,
    )

    assert len(relationships) == 1