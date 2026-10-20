import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from claimgraph.comparison_pipeline import compare_claims
from claimgraph.graph_builder import build_claim_graph
from claimgraph.models import Claim
from claimgraph.pdf_processor import extract_text_from_pdf
from claimgraph.claim_extractor import extract_claims_with_gemini


st.set_page_config(
    page_title="ClaimGraph AI",
    page_icon="ðŸ”Ž",
    layout="wide",
)


st.title("ðŸ”Ž ClaimGraph AI")
st.subheader("Evidence-based claim analysis across documents")

st.write(
    "Upload research papers or reports to extract factual claims, "
    "analyze relationships, and explore the supporting evidence."
)

st.info(
    "This prototype uses Gemini API calls to extract and compare claims. "
    "Start with short, text-based PDFs to limit processing time and API usage."
)


uploaded_files = st.file_uploader(
    "Upload PDF documents",
    type=["pdf"],
    accept_multiple_files=True,
)


def create_graph_html(graph):
    """Convert a NetworkX graph into interactive HTML."""

    network = Network(
        height="650px",
        width="100%",
        directed=False,
        bgcolor="#111827",
        font_color="white",
        cdn_resources="in_line",
    )

    network.from_nx(graph)

    relation_colors = {
        "CONTRADICTS": "#ef4444",
        "SUPPORTS": "#22c55e",
        "QUALIFIES": "#f59e0b",
        "UNRELATED": "#9ca3af",
        "INSUFFICIENT_EVIDENCE": "#a78bfa",
        "CONTAINS": "#60a5fa",
    }

    for node in network.nodes:
        node_type = node.get("node_type", "claim")

        if node_type == "document":
            node["color"] = "#2563eb"
            node["shape"] = "box"
            node["label"] = node.get("document_name", node["id"])
            node["title"] = node.get("document_name", node["id"])

        else:
            full_text = node.get("text", "")
            node["color"] = "#14b8a6"
            node["shape"] = "dot"
            node["label"] = (
                full_text[:65] + "..."
                if len(full_text) > 65
                else full_text
            )

            node["title"] = (
                f"<b>Claim:</b> {full_text}<br>"
                f"<b>Document:</b> {node.get('document_name', '')}<br>"
                f"<b>Page:</b> {node.get('page_number', '')}<br>"
                f"<b>Evidence:</b> {node.get('evidence_text', '')}"
            )

    for edge in network.edges:
        relation_type = edge.get("relation_type", "RELATED")

        edge["label"] = relation_type
        edge["color"] = relation_colors.get(
            relation_type,
            "#9ca3af",
        )

        edge["title"] = edge.get(
            "explanation",
            relation_type,
        )

    network.set_options(
        """
        {
          "physics": {
            "enabled": true,
            "stabilization": {
              "iterations": 150
            }
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          },
          "edges": {
            "font": {
              "size": 10,
              "color": "#e5e7eb",
              "strokeWidth": 0
            },
            "smooth": {
              "type": "dynamic"
            }
          }
        }
        """
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        html_path = Path(temp_dir) / "claimgraph.html"

        network.write_html(
            str(html_path),
            open_browser=False,
            notebook=False,
        )

        return html_path.read_text(encoding="utf-8")


if uploaded_files:
    st.write(f"**Documents selected:** {len(uploaded_files)}")

    for uploaded_file in uploaded_files:
        st.write(f"ðŸ“„ {uploaded_file.name}")

    if len(uploaded_files) < 2:
        st.warning(
            "Upload at least two PDFs to compare claims across documents."
        )

    if st.button(
        "ðŸš€ Analyze Documents",
        type="primary",
        use_container_width=True,
    ):
        all_claims = []
        processing_errors = []

        with tempfile.TemporaryDirectory() as temp_dir:
            for index, uploaded_file in enumerate(uploaded_files):
                st.write(f"Processing **{uploaded_file.name}**...")

                safe_name = Path(uploaded_file.name).name

                # Use a unique temporary filename to avoid collisions.
                pdf_path = (
                    Path(temp_dir)
                    / f"{index}_{safe_name}"
                )

                pdf_path.write_bytes(uploaded_file.getvalue())

                try:
                    pages = extract_text_from_pdf(pdf_path)

                    claims = extract_claims_with_gemini(
                        pages,
                        uploaded_file.name,
                    )

                    all_claims.extend(claims)

                    st.success(
                        f"{uploaded_file.name}: "
                        f"{len(claims)} claims extracted."
                    )

                except Exception as exc:
                    processing_errors.append(
                        f"{uploaded_file.name}: {exc}"
                    )

        if processing_errors:
            st.error(
                "Some documents could not be processed. "
                "Review the errors below."
            )

            for error in processing_errors:
                st.write(f"- {error}")

        if not all_claims:
            st.warning(
                "No claims were extracted successfully. "
                "Check your PDFs and Gemini API configuration."
            )

        else:
            st.session_state["claims"] = all_claims
            st.session_state["relationships"] = []
            st.session_state["graph"] = None

            st.success(
                f"Extraction complete: {len(all_claims)} claims found."
            )

            if len(uploaded_files) < 2:
                st.info(
                    "Upload multiple documents to discover "
                    "cross-document relationships."
                )


claims = st.session_state.get("claims", [])

if claims:
    st.divider()
    st.header("ðŸ“‘ Extracted Claims")

    st.metric("Total claims", len(claims))

    claim_table = [
        {
            "Claim ID": claim.claim_id,
            "Claim": claim.text,
            "Document": claim.document_name,
            "Page": claim.page_number,
            "Evidence": claim.evidence_text,
        }
        for claim in claims
    ]

    st.dataframe(
        claim_table,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.header("ðŸ”— Relationship Analysis")

    document_names = {
        claim.document_name
        for claim in claims
    }

    if len(document_names) < 2:
        st.info(
            "Relationships are compared across different documents. "
            "Upload at least two documents to continue."
        )

    elif st.button(
        "Analyze Claim Relationships",
        type="primary",
        use_container_width=True,
    ):
        total_possible_pairs = sum(
            1
            for i, claim_a in enumerate(claims)
            for claim_b in claims[i + 1:]
            if claim_a.document_name != claim_b.document_name
        )

        st.write(
            f"Eligible cross-document claim pairs: "
            f"{total_possible_pairs}"
        )

        if total_possible_pairs > 100:
            st.warning(
                "This comparison could require many Gemini API calls. "
                "Consider using shorter documents for this prototype."
            )

        try:
            with st.spinner(
                "Analyzing claim relationships with Gemini..."
            ):
                relationships = compare_claims(claims)

            graph = build_claim_graph(
                claims,
                relationships,
            )

            st.session_state["relationships"] = relationships
            st.session_state["graph"] = graph

            st.success(
                f"Analysis complete: "
                f"{len(relationships)} relationships identified."
            )

        except Exception as exc:
            st.error(f"Relationship analysis failed: {exc}")


relationships = st.session_state.get("relationships", [])
graph = st.session_state.get("graph")

if relationships and graph is not None:
    st.divider()
    st.header("ðŸŒ Interactive Knowledge Graph")

    relation_types = sorted(
        {relationship.relation_type for relationship in relationships}
    )

    selected_types = st.multiselect(
        "Filter relationships",
        options=relation_types,
        default=relation_types,
    )

    filtered_relationships = [
        relationship
        for relationship in relationships
        if relationship.relation_type in selected_types
    ]

    filtered_graph = build_claim_graph(
        claims,
        filtered_relationships,
    )

    graph_html = create_graph_html(filtered_graph)

    components.html(
        graph_html,
        height=700,
        scrolling=True,
    )

    st.caption(
        "Hover over nodes for claim details. "
        "Drag nodes to explore connections."
    )

    st.divider()
    st.header("ðŸ“Š Relationship Summary")

    summary_columns = st.columns(3)

    summary_columns[0].metric(
        "Claims",
        len(claims),
    )

    summary_columns[1].metric(
        "Relationships",
        len(relationships),
    )

    summary_columns[2].metric(
        "Documents",
        len({claim.document_name for claim in claims}),
    )

    for relation_type in relation_types:
        count = sum(
            1
            for relationship in relationships
            if relationship.relation_type == relation_type
        )

        st.write(f"**{relation_type}:** {count}")

    st.divider()
    st.header("ðŸ” Inspect Relationship Evidence")

    if not filtered_relationships:
        st.info("No relationships match the selected filters.")

    else:
        relationship_options = [
            (
                f"{relationship.source_claim_id} â†’ "
                f"{relationship.target_claim_id} "
                f"({relationship.relation_type})"
            )
            for relationship in filtered_relationships
        ]

        selected_index = st.selectbox(
            "Select a relationship",
            range(len(relationship_options)),
            format_func=lambda index: relationship_options[index],
        )

        selected_relationship = filtered_relationships[selected_index]

        claims_by_id = {
            claim.claim_id: claim
            for claim in claims
        }

        source_claim = claims_by_id[
            selected_relationship.source_claim_id
        ]

        target_claim = claims_by_id[
            selected_relationship.target_claim_id
        ]

        left, right = st.columns(2)

        with left:
            st.subheader("Source Claim")
            st.write(source_claim.text)
            st.caption(
                f"{source_claim.document_name}, "
                f"page {source_claim.page_number}"
            )
            st.info(source_claim.evidence_text)

        with right:
            st.subheader("Target Claim")
            st.write(target_claim.text)
            st.caption(
                f"{target_claim.document_name}, "
                f"page {target_claim.page_number}"
            )
            st.info(target_claim.evidence_text)

        st.subheader(
            f"Relationship: {selected_relationship.relation_type}"
        )

        st.write(selected_relationship.explanation)

else:
    if claims:
        st.info(
            "Claims are ready. Analyze their relationships to "
            "generate the interactive knowledge graph."
        )
    else:
        st.info(
            "Upload two or more text-based PDFs to get started."
        )


st.divider()

st.caption(
    "ClaimGraph AI | AI-generated classifications should be verified "
    "against the original source documents."
)
