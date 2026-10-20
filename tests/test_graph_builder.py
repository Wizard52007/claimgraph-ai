import pytest

from claimgraph.graph_builder import build_claim_graph
from claimgraph.models import Claim, ClaimRelationship


def make_claim(claim_id, document_name, text):
    return Claim(
        claim_id=claim_id,
        text=text,
        document_name=document_name,
        page_number=1,
        evidence_text=text,
    )


def make_relationship(source_id, target_id, relation_type):
    return ClaimRelationship(
        source_claim_id=source_id,
        target_claim_id=target_id,
        relation_type=relation_type,
        explanation="Example relationship.",
        source_evidence="Source evidence.",
        target_evidence="Target evidence.",
    )


def test_graph_contains_document_and_claim_nodes():
    claims = [
        make_claim("claim_a", "report_a.pdf", "Solar capacity reached 100 GW."),
        make_claim("claim_b", "report_b.pdf", "Solar capacity reached 80 GW."),
    ]

    graph = build_claim_graph(claims, [])

    assert "document::report_a.pdf" in graph
    assert "document::report_b.pdf" in graph
    assert "claim_a" in graph
    assert "claim_b" in graph


def test_claim_is_connected_to_its_document():
    claim = make_claim(
        "claim_a",
        "report_a.pdf",
        "Solar capacity reached 100 GW.",
    )

    graph = build_claim_graph([claim], [])

    assert graph.has_edge("document::report_a.pdf", "claim_a")
    assert graph["document::report_a.pdf"]["claim_a"]["relation_type"] == "CONTAINS"


def test_claim_relationship_is_added_to_graph():
    claims = [
        make_claim("claim_a", "report_a.pdf", "Solar capacity reached 100 GW."),
        make_claim("claim_b", "report_b.pdf", "Solar capacity reached 80 GW."),
    ]

    relationship = make_relationship(
        "claim_a",
        "claim_b",
        "CONTRADICTS",
    )

    graph = build_claim_graph(claims, [relationship])

    assert graph.has_edge("claim_a", "claim_b")
    assert graph["claim_a"]["claim_b"]["relation_type"] == "CONTRADICTS"


def test_claim_evidence_is_preserved_in_node():
    claim = make_claim(
        "claim_a",
        "report_a.pdf",
        "Solar capacity reached 100 GW.",
    )

    graph = build_claim_graph([claim], [])

    assert graph.nodes["claim_a"]["evidence_text"] == claim.evidence_text
    assert graph.nodes["claim_a"]["page_number"] == 1


def test_relationship_with_missing_claim_is_rejected():
    claim = make_claim(
        "claim_a",
        "report_a.pdf",
        "Solar capacity reached 100 GW.",
    )

    relationship = make_relationship(
        "claim_a",
        "missing_claim",
        "CONTRADICTS",
    )

    with pytest.raises(ValueError, match="claim that is missing"):
        build_claim_graph([claim], [relationship])


def test_empty_input_creates_empty_graph():
    graph = build_claim_graph([], [])

    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0