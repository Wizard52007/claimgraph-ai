import logging
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from claimgraph.claim_extractor import extract_claims_with_gemini
from claimgraph.comparison_pipeline import compare_claims
from claimgraph.graph_builder import build_claim_graph
from claimgraph.pdf_processor import extract_text_from_pdf


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ClaimGraph AI API",
    description="Evidence-based claim analysis across documents.",
    version="1.0.0",
)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Check whether the API is running."""
    return {"status": "healthy"}


@app.post("/analyze")
async def analyze_documents(
    files: Annotated[
        list[UploadFile],
        File(description="Select two or more PDF files"),
    ],
):
    """Extract claims and analyze relationships across uploaded PDFs."""

    if len(files) < 2:
        raise HTTPException(
            status_code=400,
            detail="Upload at least two PDF documents.",
        )

    all_claims = []
    processing_errors = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for index, uploaded_file in enumerate(files):
            filename = Path(uploaded_file.filename or "").name

            if not filename.lower().endswith(".pdf"):
                processing_errors.append(
                    f"{filename or 'Unnamed file'}: Only PDF files are supported."
                )
                continue

            try:
                content = await uploaded_file.read()

                if not content:
                    raise ValueError("The uploaded file is empty.")

                pdf_path = temp_path / f"{index}_{filename}"
                pdf_path.write_bytes(content)

                pages = extract_text_from_pdf(pdf_path)

                claims = extract_claims_with_gemini(
                    pages,
                    filename,
                )

                all_claims.extend(claims)

                logger.info(
                    "Extracted %d claims from %s",
                    len(claims),
                    filename,
                )

            except Exception:
                logger.exception("Failed to process %s", filename)
                processing_errors.append(
                    f"{filename}: Document processing failed."
                )

            finally:
                await uploaded_file.close()

    if processing_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    "One or more documents could not be processed. "
                    "No partial analysis was returned."
                ),
                "errors": processing_errors,
            },
        )

    if not all_claims:
        raise HTTPException(
            status_code=422,
            detail="No claims were extracted from the uploaded PDFs.",
        )

    try:
        relationships = compare_claims(all_claims)

        graph = build_claim_graph(
            all_claims,
            relationships,
        )

        graph_nodes = [
            {
                "id": str(node_id),
                **attributes,
            }
            for node_id, attributes in graph.nodes(data=True)
        ]

        graph_edges = [
            {
                "source": str(source),
                "target": str(target),
                **attributes,
            }
            for source, target, attributes in graph.edges(data=True)
        ]

        return {
            "claims": [
                claim.model_dump()
                for claim in all_claims
            ],
            "relationships": [
                relationship.model_dump()
                for relationship in relationships
            ],
            "graph": {
                "nodes": graph_nodes,
                "edges": graph_edges,
            },
            "summary": {
                "document_count": len(files),
                "claim_count": len(all_claims),
                "relationship_count": len(relationships),
                "potential_contradictions": sum(
                    relationship.relation_type == "CONTRADICTS"
                    for relationship in relationships
                ),
            },
        }

    except Exception as exc:
        logger.exception("Claim analysis failed")

        raise HTTPException(
            status_code=500,
            detail="Claim analysis failed. Check the server logs.",
        ) from exc