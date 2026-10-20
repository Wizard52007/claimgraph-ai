from itertools import combinations

from claimgraph.models import Claim, ClaimRelationship
from claimgraph.relationship_analyzer import analyze_relationship


def compare_claims(
    claims: list[Claim],
    cross_document_only: bool = True,
) -> list[ClaimRelationship]:
    """Compare claim pairs and return their classified relationships."""

    relationships = []

    for claim_a, claim_b in combinations(claims, 2):
        if claim_a.claim_id == claim_b.claim_id:
            continue

        if (
            cross_document_only
            and claim_a.document_name == claim_b.document_name
        ):
            continue

        relationship = analyze_relationship(claim_a, claim_b)
        relationships.append(relationship)

    return relationships