import requests
from pathlib import Path

API_URL = "https://claimgraph-ai.onrender.com/analyze"

pdf_paths = [
    Path("../paper_a.pdf"),
    Path("../paper_b.pdf"),
]

files = []

try:
    for path in pdf_paths:
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path.resolve()}")

        files.append(
            ("files", (path.name, open(path, "rb"), "application/pdf"))
        )

    print("Sending PDFs to deployed backend...")

    response = requests.post(
        API_URL,
        files=files,
        timeout=300,
    )

    print("HTTP Status:", response.status_code)
    print("Response:")
    print(response.text[:10000])

finally:
    for _, (_, file_object, _) in files:
        file_object.close()