import networkx as nx

from claimgraph.models import Claim, ClaimRelationship


def build_claim_graph(
    claims: list[Claim],
    relationships: list[ClaimRelationship],
) -> nx.Graph:
    """Build a graph containing documents, claims, and relationships."""

    graph = nx.Graph()

    # Add one node for every source document.
    for claim in claims:
        document_id = f"document::{claim.document_name}"

        graph.add_node(
            document_id,
            node_type="document",
            label=claim.document_name,
            document_name=claim.document_name,
        )

    # Add claim nodes and connect them to their source documents.
    for claim in claims:
        document_id = f"document::{claim.document_name}"

        graph.add_node(
            claim.claim_id,
            node_type="claim",
            label=claim.text,
            text=claim.text,
            document_name=claim.document_name,
            page_number=claim.page_number,
            evidence_text=claim.evidence_text,
        )

        graph.add_edge(
            document_id,
            claim.claim_id,
            relation_type="CONTAINS",
        )

    # Add relationships between claims.
    for relationship in relationships:
        source_id = relationship.source_claim_id
        target_id = relationship.target_claim_id

        if source_id not in graph or target_id not in graph:
            raise ValueError(
                "A relationship references a claim that is missing from the graph."
            )

        graph.add_edge(
            source_id,
            target_id,
            relation_type=relationship.relation_type,
            explanation=relationship.explanation,
            source_evidence=relationship.source_evidence,
            target_evidence=relationship.target_evidence,
        )

    return graph