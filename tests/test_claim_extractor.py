from claimgraph.claim_extractor import extract_claims


def test_extract_claims_from_single_page():
    pages = [
        {
            "page_number": 1,
            "text": "Solar capacity reached 100 GW in 2025. Renewable energy is growing.",
        }
    ]

    claims = extract_claims(pages, "energy_report.pdf")

    assert len(claims) == 2
    assert claims[0].text == "Solar capacity reached 100 GW in 2025."
    assert claims[0].page_number == 1
    assert claims[0].document_name == "energy_report.pdf"
    assert claims[0].evidence_text == claims[0].text
    assert claims[0].claim_id == "energy_report_claim_001"


def test_extract_claims_preserves_page_numbers():
    pages = [
        {"page_number": 1, "text": "Solar energy is growing."},
        {"page_number": 2, "text": "Wind energy is growing."},
    ]

    claims = extract_claims(pages, "report.pdf")

    assert len(claims) == 2
    assert claims[0].page_number == 1
    assert claims[1].page_number == 2


def test_empty_pages_return_no_claims():
    claims = extract_claims([], "empty_report.pdf")

    assert claims == []
