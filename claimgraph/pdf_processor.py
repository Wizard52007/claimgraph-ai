from pathlib import Path

import pymupdf


def extract_text_from_pdf(pdf_path: str | Path) -> list[dict]:
    """Extract text from a PDF while preserving page numbers."""
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("The supplied file must be a PDF.")

    pages = []

    with pymupdf.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()

            if text:
                pages.append({
                    "page_number": page_number,
                    "text": text,
                })

    if not pages:
        raise ValueError("No extractable text found. The PDF may be empty or scanned.")

    return pages
