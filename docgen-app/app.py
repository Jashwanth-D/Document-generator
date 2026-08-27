"""
app.py
DocAgent — Integration Document Generator
Team opens this URL, pastes a requirement, downloads BRD + TDD.
"""

import streamlit as st
from llm_parser import parse_requirement
from doc_generator import generate_brd, generate_tdd
from datetime import datetime
import json

# ── Page Config ──
st.set_page_config(
    page_title="DocAgent",
    page_icon="📄",
    layout="centered",
)

# ── Init session state ──
if "generated" not in st.session_state:
    st.session_state.generated = False
if "brd_bytes" not in st.session_state:
    st.session_state.brd_bytes = None
if "tdd_bytes" not in st.session_state:
    st.session_state.tdd_bytes = None
if "canonical" not in st.session_state:
    st.session_state.canonical = None
if "validation" not in st.session_state:
    st.session_state.validation = None
if "cross" not in st.session_state:
    st.session_state.cross = None
if "safe_name" not in st.session_state:
    st.session_state.safe_name = "Integration"
if "last_requirement" not in st.session_state:
    st.session_state.last_requirement = ""

# ── Styling ──
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1F3864;
        margin-bottom: 0;
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 14px;
        margin-top: -10px;
        margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("<h1 class='main-header'>📄 DocAgent</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>Integration Document Generator — Paste a requirement, get BRD + TDD</p>", unsafe_allow_html=True)

# ── API Key ──
api_key = None
try:
    api_key = st.secrets.get("GROQ_API_KEY", None)
except:
    pass

if not api_key:
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        api_key = st.text_input("Groq API Key", type="password", help="Get your free key at console.groq.com")
        st.markdown("---")
        st.markdown("**How to get a free API key:**")
        st.markdown("1. Go to [console.groq.com](https://console.groq.com)")
        st.markdown("2. Sign up (free)")
        st.markdown("3. Create an API key")
        st.markdown("4. Paste it above")

# ── Helper ──
def v(field):
    if field is None:
        return "TBD"
    if isinstance(field, str):
        return field
    if isinstance(field, dict) and "value" in field:
        return str(field["value"])
    return "TBD"

# ── Main Input ──
st.markdown("### Enter Integration Requirement")
requirement = st.text_area(
    "Paste or type the requirement below:",
    height=120,
    placeholder="Example: Create an integration that reads purchase order files from an SFTP server and loads them into the ERP database for procurement processing.",
)

# ── Generate Button ──
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    generate = st.button("🚀 Generate Documents", use_container_width=True, type="primary")

# ── Processing ──
if generate:
    if not api_key:
        st.error("Please enter your Groq API key in the sidebar.")
        st.stop()

    if not requirement.strip():
        st.error("Please enter a requirement.")
        st.stop()

    # Clear previous results
    st.session_state.generated = False

    with st.status("Generating documents...", expanded=True) as status:
        st.write("🤖 Analyzing requirement with AI...")
        try:
            result = parse_requirement(requirement.strip(), api_key)
        except Exception as e:
            st.error(f"LLM parsing failed: {str(e)}")
            st.stop()

        canonical = result["canonical"]
        validation = result["validation"]
        cross = result["crossValidation"]

        st.write("📋 Extraction complete. Generating documents...")

        try:
            brd_buffer = generate_brd(canonical)
            tdd_buffer = generate_tdd(canonical)
        except Exception as e:
            st.error(f"Document generation failed: {str(e)}")
            st.stop()

        # Store everything in session state
        project_name = v(canonical.get("project", {}).get("name", "Integration"))
        safe_name = "".join(c if c.isalnum() or c in "_ " else "_" for c in project_name)[:50]

        st.session_state.brd_bytes = brd_buffer.getvalue()
        st.session_state.tdd_bytes = tdd_buffer.getvalue()
        st.session_state.canonical = canonical
        st.session_state.validation = validation
        st.session_state.cross = cross
        st.session_state.safe_name = safe_name
        st.session_state.last_requirement = requirement.strip()
        st.session_state.generated = True

        status.update(label="✅ Documents ready!", state="complete", expanded=True)

# ── Show Results (persists across reruns) ──
if st.session_state.generated:
    canonical = st.session_state.canonical
    validation = st.session_state.validation
    cross = st.session_state.cross
    safe_name = st.session_state.safe_name

    st.markdown("---")
    st.markdown("### 📊 Extraction Summary")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**What was extracted:**")
        st.markdown(f"- **Source:** {v(canonical.get('source', {}).get('system'))}")
        st.markdown(f"- **Target:** {v(canonical.get('target', {}).get('system'))}")
        st.markdown(f"- **Work Type:** {v(canonical.get('integration', {}).get('workType'))}")
        st.markdown(f"- **Direction:** {v(canonical.get('integration', {}).get('direction'))}")
        st.markdown(f"- **Pattern:** {v(canonical.get('integration', {}).get('pattern'))}")
        entities = ", ".join(v(e) for e in canonical.get("entities", []))
        st.markdown(f"- **Entities:** {entities}")

    with col_b:
        st.markdown("**Key TBDs:**")
        for item in canonical.get("unresolvedItems", [])[:8]:
            st.markdown(f"- {item}")

    # Validation status
    if cross["status"] == "PASS":
        st.success("✅ Cross-validation passed — BRD and TDD are consistent.")
    else:
        st.warning("⚠️ Cross-validation: REVIEW REQUIRED")
        for issue in cross["issues"]:
            st.markdown(f"- {issue}")

    if validation["issues"]:
        with st.expander("⚠️ Anti-hallucination check notes"):
            for issue in validation["issues"]:
                st.markdown(f"- {issue}")

    # Download buttons
    st.markdown("### 📥 Download Documents")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📘 Download BRD.docx",
            data=st.session_state.brd_bytes,
            file_name=f"BRD_{safe_name}_v1_0.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    with col2:
        st.download_button(
            label="📗 Download TDD.docx",
            data=st.session_state.tdd_bytes,
            file_name=f"TDD_{safe_name}_v1_0.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    # Canonical JSON viewer
    with st.expander("🔍 View full canonical JSON (for debugging)"):
        st.json(canonical)

    # Clear button
    st.markdown("---")
    if st.button("🔄 Start New Requirement"):
        st.session_state.generated = False
        st.session_state.brd_bytes = None
        st.session_state.tdd_bytes = None
        st.session_state.canonical = None
        st.session_state.validation = None
        st.session_state.cross = None
        st.rerun()

# ── Footer ──
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #999; font-size: 12px;'>"
    "DocAgent v1.0 — AI-powered integration document generator. "
    "All unknown fields are marked TBD — nothing is hallucinated."
    "</p>",
    unsafe_allow_html=True,
)
