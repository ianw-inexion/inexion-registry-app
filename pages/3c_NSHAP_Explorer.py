"""
NSHAP Explorer - placeholder page.

Pipeline is scaffolded (build_nshap_parquet.py in inexion-registry-pipeline);
data will land here once Anant completes the ICPSR download / DUA process.

When the three parquets are present, this page should mirror the MIDUS
Explorer pattern: tabs for Overview, Biomarker Panel, Social Network +
Sensory, Wave Comparison, Cognition. Each round (R1 2006 - R4 2023)
contributes data; longitudinal subset is the R1 returnee cohort.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from src.config import (data_exists, NAVY, GOLD, CORAL, TEAL,
                        NSHAP_BIO_PARQUET, NSHAP_SOCIAL_PARQUET,
                        NSHAP_CODEBOOK_PARQUET)

st.set_page_config(page_title="NSHAP Explorer - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            NSHAP Explorer
            <span style='font-size:14px;color:{GOLD};font-weight:500;letter-spacing:0;
                margin-left:12px;'>- pipeline scaffolded, awaiting data</span></div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            National Social Life, Health, and Aging Project &middot; 4 rounds 2005-2023 &middot;
            DBS biomarkers + saliva cortisol + social network + sensory measures
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_codebook():
    if not data_exists(NSHAP_CODEBOOK_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(NSHAP_CODEBOOK_PARQUET)


@st.cache_data
def load_bio():
    if not data_exists(NSHAP_BIO_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(NSHAP_BIO_PARQUET)


@st.cache_data
def load_social():
    if not data_exists(NSHAP_SOCIAL_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(NSHAP_SOCIAL_PARQUET)


bio = load_bio()
soc = load_social()
cb  = load_codebook()

if bio.empty:
    # Data not yet ingested. Show the scaffold + roadmap so the page is
    # informative rather than blank.
    st.info(
        "**NSHAP biomarker parquet not yet present.** Pipeline is scaffolded in "
        "`inexion-registry-pipeline/build_nshap_parquet.py`. Once Anant downloads "
        "the ICPSR Stata distributions and places them under "
        "`data/raw/nshap/round_<n>/DS0001/`, running the pipeline will populate "
        "this page."
    )

    st.markdown("#### Schema preview (from codebook)")
    if cb.empty:
        st.warning("Codebook parquet not found either. Run "
                    "`python build_nshap_parquet.py` once to materialize the schema.")
    else:
        st.caption(
            "Per-round variable coverage table built from the harmonization map. "
            "Coverage of '4' = harmonized variable expected across all 4 rounds; "
            "'2' = available only in Rounds 3 and 4 (newer panels)."
        )
        st.dataframe(cb, width='stretch', hide_index=True)

        st.markdown("##### Coverage histogram")
        cov = cb.groupby(['category', 'rounds_with_data']).size().reset_index(name='count')
        fig = px.bar(cov, x='rounds_with_data', y='count', color='category',
                      color_discrete_map={'biomarker': NAVY, 'social': GOLD},
                      labels={'rounds_with_data': 'Rounds the variable spans',
                              'count': 'Variables'},
                      title='Harmonized-variable coverage across NSHAP rounds')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                          font_color='#1A1A2E', height=320)
        st.plotly_chart(fig, width='stretch')

    st.markdown("---")
    st.markdown("#### Acquisition roadmap")
    st.markdown(
        "**ICPSR Study IDs:**  \n"
        "- Round 1 (2005-06): 20541  \n"
        "- Round 2 (2010-11): 34921  \n"
        "- Round 3 (2015-16): 36873 (also includes COVID-19 sub-study 2020-21)  \n"
        "- Round 4 (2021-23): 39511  \n  \n"
        "**Public-use** files: ICPSR registration is sufficient. Free download.  \n"
        "**Restricted-use** files (NDI mortality linkage, geocoded variables, "
        "raw social-network roster): require IRB + Data Protection Plan + signed DUA.  \n  \n"
        "**Once data lands:**  \n"
        "1. Run `python build_nshap_parquet.py` from the pipeline repo.  \n"
        "2. Sync parquets to S3 via `scripts/deploy.ps1`.  \n"
        "3. This page will auto-light-up - no app code changes needed.  \n"
        "4. Add NSHAP as a 4th dataset option in the Research Workbench.  \n"
        "5. Score Phase 4 Metabolic Age on NSHAP (HbA1c + total chol + BMI + BP "
        "from R2+; HDL only R3+) and add cross-cohort validation tile to the "
        "Validation page."
    )
    st.stop()


# ---- Once data is present, the rest of this page renders ----
st.markdown(f"**{len(bio):,} biomarker observations across {bio['round'].nunique()} rounds**")
st.dataframe(bio.head(50), width='stretch')

if not soc.empty:
    st.markdown(f"**Social / sensory / functional measures: {len(soc):,} observations**")
    st.dataframe(soc.head(50), width='stretch')

st.caption(
    "NSHAP - National Social Life, Health, and Aging Project. 4 rounds 2005-2023, "
    "ages 57-85 at baseline. Public-use via ICPSR; restricted-use NDI mortality "
    "linkage requires IRB + DPP + DUA."
)
