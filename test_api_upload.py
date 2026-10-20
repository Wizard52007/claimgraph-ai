import httpx
from pathlib import Path

API_URL = "http://127.0.0.1:8000/analyze"

PDF_A = Path("..") / "paper_a.pdf"
PDF_B = Path("..") / "paper_b.pdf"

if not PDF_A.exists() or not PDF_B.exists():
    print("ERROR: Test PDFs not found.")
    print("PDF A:", PDF_A.resolve(), PDF_A.exists())
    print("PDF B:", PDF_B.resolve(), PDF_B.exists())
    raise SystemExit(1)

with PDF_A.open("rb") as file_a, PDF_B.open("rb") as file_b:
    files = [
        ("files", ("paper_a.pdf", file_a, "application/pdf")),
        ("files", ("paper_b.pdf", file_b, "application/pdf")),
    ]

    try:
        response = httpx.post(
            API_URL,
            files=files,
            timeout=300.0,
        )
        print("HTTP status:", response.status_code)
        print("Response:")
        print(response.text)
    except httpx.RequestError as exc:
        print("Request failed:", exc)
