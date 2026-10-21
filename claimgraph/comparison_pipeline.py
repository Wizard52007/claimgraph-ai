from itertools import combinations

from claimgraph.models import Claim, ClaimRelationship
from claimgraph.relationship_analyzer import analyze_relationship


# Maximum number of AI comparisons per analysis
MAX_COMPARISONS = 20


def compare_claims(
    claims: list[Claim],
    cross_document_only: bool = True,
) -> list[ClaimRelationship]:
    """Compare claim pairs and return their classified relationships."""

    relationships = []
    comparisons_made = 0

    for claim_a, claim_b in combinations(claims, 2):
        if claim_a.claim_id == claim_b.claim_id:
            continue

        if (
            cross_document_only
            and claim_a.document_name == claim_b.document_name
        ):
            continue

        if comparisons_made >= MAX_COMPARISONS:
            break

        relationship = analyze_relationship(claim_a, claim_b)
        relationships.append(relationship)
        comparisons_made += 1

    return relationships