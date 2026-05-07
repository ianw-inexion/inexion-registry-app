"""
INEXION Longevity Registry — prototype app.

Entry point. Renders the landing / home page and configures the shared
sidebar. Other pages live under pages/ and are auto-registered by Streamlit.
"""
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from src.config import (
    APP_TITLE, APP_TAGLINE, APP_VERSION, NAVY, GOLD, DARK_TEXT,
)
from src import data


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=":dna:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Brand-aligned header
st.markdown(
    f"""
    <div style='padding: 18px 24px; background: {NAVY}; border-radius: 8px;
                margin-bottom: 24px;'>
        <div style='color: {GOLD}; font-size: 13px; letter-spacing: 2px;
                    text-transform: uppercase; font-weight: 600;'>INEXION</div>
        <div style='color: white; font-size: 28px; font-weight: 700;
                    margin-top: 4px;'>{APP_TITLE}</div>
        <div style='color: #C9CBD4; font-size: 14px; margin-top: 4px;'>
            {APP_TAGLINE} &nbsp;·&nbsp; v{APP_VERSION}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"**{APP_TITLE}**")
    st.caption(f"v{APP_VERSION}")
    st.markdown("---")
    st.markdown(
        "**Pages**\n\n"
        "- Dataset Catalog\n"
        "- Cohort Builder\n"
        "- Variable Dictionary\n"
        "- Biological Age Calculator\n"
        "- Admin"
    )
    st.markdown("---")
    st.caption(
        "Prototype build. Auth, audit logging, and remote object storage "
        "added in deployment phase."
    )


# ── Landing ──────────────────────────────────────────────────────────────────
try:
    stats = data.dataset_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Participants (NHANES)", f"{int(stats['n_total']):,}")
    c2.metric("With PhenoAge", f"{int(stats['n_with_phenoage']):,}")
    c3.metric("With KDM bioage", f"{int(stats['n_with_kdm']):,}")
    c4.metric("Cycles", f"{int(stats['n_cycles'])} ({int(stats['min_year'])}–{int(stats['max_year'])})")
except Exception as e:
    st.error(
        "Data not found. Ensure `data/staging/nhanes_with_phenoage.parquet` "
        "exists in the pipeline repo, or set `INEXION_DATA_DIR`.\n\n"
        f"Details: {e}"
    )
    st.stop()


st.markdown("### What this is")
st.markdown(
    "A working prototype of the INEXION Longevity Registry app. The registry "
    "aggregates de-identified biomarker and outcomes data across public "
    "reference datasets today, and will ingest data from the INEXION clinic "
    "network as it comes online."
)

st.markdown("### What you can do right now")
left, right = st.columns(2)
with left:
    st.markdown(
        "**Browse datasets** on the Dataset Catalog page — see what's "
        "available, what's gated, and what's pending.\n\n"
        "**Build a cohort** on the Cohort Builder page — apply demographic "
        "and biomarker filters, see live counts, view descriptive summaries, "
        "and export the slice as CSV."
    )
with right:
    st.markdown(
        "**Look up any variable** on the Variable Dictionary page — units, "
        "definitions, grouping.\n\n"
        "**Run the calculator** on the Biological Age Calculator page — "
        "paste in a patient's lab values and return PhenoAge + delta."
    )

st.markdown("### Roadmap — what this becomes")
st.markdown(
    "- **Today (v0.2 prototype):** NHANES only, running locally, no auth. "
    "This is the click-through surface for stakeholder review.\n"
    "- **v0.3 (deployed):** `registry.inexion.com/app` behind Google SSO "
    "and magic-link invite. Audit logging, object-storage backend, "
    "public shell at `registry.inexion.com`.\n"
    "- **v0.4+:** HRS, UK Biobank, CALERIE, GEO added as access lands. "
    "Saved cohort queries. Researcher-facing documentation.\n"
    "- **v1.0:** Clinic data ingestion adapter. This is when the registry "
    "stops being a proof of capability and starts being the product."
)

st.markdown("---")
st.caption(
    "This prototype reads directly from the pipeline's parquet output. "
    "No PHI is present. All source data is from de-identified public datasets."
)
