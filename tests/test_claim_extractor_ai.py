import json

import pytest

from claimgraph.claim_extractor import extract_claims_with_gemini


def test_gemini_extracts_claim_with_verified_evidence(monkeypatch):
    source_text = "Solar capacity reached 100 GW in 2025."

    simulated_response = [
        {
            "text": "Solar capacity reached 100 GW in 2025.",
            "evidence_text": "Solar capacity reached 100 GW in 2025.",
        }
    ]

    monkeypatch.setattr(
        "claimgraph.claim_extractor.generate_text",
        lambda prompt: json.dumps(simulated_response),
    )

    pages = [
        {
            "page_number": 2,
            "text": source_text,
        }
    ]

    claims = extract_claims_with_gemini(
        pages,
        "energy_report.pdf",
    )

    assert len(claims) == 1
    assert claims[0].text == simulated_response[0]["text"]
    assert claims[0].document_name == "energy_report.pdf"
    assert claims[0].page_number == 2
    assert claims[0].evidence_text == source_text


def test_gemini_claim_with_fabricated_evidence_is_rejected(monkeypatch):
    simulated_response = [
        {
            "text": "Solar capacity reached 200 GW.",
            "evidence_text": "Solar capacity reached 200 GW.",
        }
    ]

    monkeypatch.setattr(
        "claimgraph.claim_extractor.generate_text",
        lambda prompt: json.dumps(simulated_response),
    )

    pages = [
        {
            "page_number": 1,
            "text": "Solar capacity reached 100 GW in 2025.",
        }
    ]

    with pytest.raises(ValueError, match="evidence could not be verified"):
        extract_claims_with_gemini(pages, "energy_report.pdf")


def test_gemini_empty_array_returns_no_claims(monkeypatch):
    monkeypatch.setattr(
        "claimgraph.claim_extractor.generate_text",
        lambda prompt: "[]",
    )

    pages = [
        {
            "page_number": 1,
            "text": "Contents and section headings.",
        }
    ]

    claims = extract_claims_with_gemini(pages, "report.pdf")

    assert claims == []


def test_gemini_invalid_json_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "claimgraph.claim_extractor.generate_text",
        lambda prompt: "This is not JSON",
    )

    pages = [
        {
            "page_number": 1,
            "text": "A sample factual statement.",
        }
    ]

    with pytest.raises(ValueError, match="invalid JSON"):
        extract_claims_with_gemini(pages, "report.pdf")