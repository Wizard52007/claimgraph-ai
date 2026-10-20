import pymupdf
import pytest

from claimgraph.pdf_processor import extract_text_from_pdf


def test_missing_pdf_raises_error():
    with pytest.raises(FileNotFoundError):
        extract_text_from_pdf("missing_file.pdf")


def test_non_pdf_file_raises_error(tmp_path):
    text_file = tmp_path / "sample.txt"
    text_file.write_text("This is not a PDF.", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a PDF"):
        extract_text_from_pdf(text_file)


def test_extract_text_from_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "ClaimGraph test document")
        document.save(pdf_path)

    pages = extract_text_from_pdf(pdf_path)

    assert len(pages) == 1
    assert pages[0]["page_number"] == 1
    assert "ClaimGraph test document" in pages[0]["text"]
