"""
INEXION Longevity Registry - app entry point.
"""
from dotenv import load_dotenv
load_dotenv()

# Streamlit Cloud: load secrets into environment
# When deployed on Streamlit Cloud, secrets are set in the dashboard and
# exposed via st.secrets. Promote them to env vars so the rest of the app
# (including src/config.py) picks them up transparently.
try:
    import streamlit as _st
    for _key in ["INEXION_DATA_DIR", "ANTHROPIC_API_KEY",
                 "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]:
        if _key in _st.secrets and _key not in __import__("os").environ:
            __import__("os").environ[_key] = _st.secrets[_key]
except Exception:
    pass

import streamlit as st
import pandas as pd
from pathlib import Path
from src.config import (data_exists,
    APP_TITLE, APP_VERSION, NAVY, GOLD, TEAL, CORAL,
    NHANES_PARQUET, HRS_VBS_PARQUET, HRS_DBS_PARQUET,
    HRS_EPIGEN_PARQUET, HRS_POA_PARQUET, HRS_PUBLIC_PARQUET,
    MIDUS_BIO_PARQUET, MIDUS_COG_PARQUET,
)

st.set_page_config(
    page_title="INEXION Longevity Registry",
    page_icon=":dna:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:24px;'>
        <div style='color:{GOLD};font-size:13px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION</div>
        <div style='color:white;font-size:28px;font-weight:700;margin-top:4px;'>
            Longevity Data Registry</div>
        <div style='color:#C9CBD4;font-size:14px;margin-top:4px;'>
            INEXION Longevity Registry &nbsp;-&nbsp; v{APP_VERSION}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.caption("Prototype build - local auth, no PHI.")

# Registry-wide stats
@st.cache_data
def get_registry_stats():
    stats = {}

    if data_exists(NHANES_PARQUET):
        df = pd.read_parquet(NHANES_PARQUET, columns=['seqn'])
        stats['nhanes_n'] = len(df)

    if data_exists(HRS_VBS_PARQUET):
        df = pd.read_parquet(HRS_VBS_PARQUET, columns=['hhidpn'])
        stats['hrs_vbs_n'] = len(df)

    if data_exists(HRS_DBS_PARQUET):
        df = pd.read_parquet(HRS_DBS_PARQUET, columns=['hhidpn'])
        stats['hrs_dbs_n'] = df['hhidpn'].nunique()
        stats['hrs_dbs_obs'] = len(df)

    if data_exists(HRS_EPIGEN_PARQUET):
        df = pd.read_parquet(HRS_EPIGEN_PARQUET, columns=['hhidpn'])
        stats['hrs_epi_n'] = len(df)

    if data_exists(HRS_POA_PARQUET):
        df = pd.read_parquet(HRS_POA_PARQUET, columns=['hhidpn'])
        stats['hrs_poa_n'] = len(df)

    if data_exists(MIDUS_BIO_PARQUET):
        df = pd.read_parquet(MIDUS_BIO_PARQUET, columns=['midus_id'])
        stats['midus_bio_n'] = len(df)

    if data_exists(MIDUS_COG_PARQUET):
        df = pd.read_parquet(MIDUS_COG_PARQUET, columns=['midus_id'])
        stats['midus_cog_n'] = len(df)

    stats['total_observations'] = (
        stats.get('nhanes_n', 0) +
        stats.get('hrs_vbs_n', 0) +
        stats.get('hrs_dbs_obs', 0) +
        stats.get('hrs_epi_n', 0) +
        stats.get('hrs_poa_n', 0) +
        stats.get('midus_bio_n', 0)
    )
    stats['datasets_loaded'] = sum(
        1 for k in ['nhanes_n','hrs_vbs_n','hrs_dbs_n','hrs_epi_n','hrs_poa_n','midus_bio_n']
        if k in stats
    )
    return stats

try:
    s = get_registry_stats()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Datasets loaded", s.get('datasets_loaded', 0))
    c2.metric("NHANES", f"{s.get('nhanes_n',0):,}")
    c3.metric("HRS VBS (PhenoAge)", f"{s.get('hrs_vbs_n',0):,}")
    c4.metric("HRS DBS respondents", f"{s.get('hrs_dbs_n',0):,}")
    c5.metric("HRS DunedinPACE", f"{s.get('hrs_poa_n',0):,}")
    c6.metric("MIDUS biomarker", f"{s.get('midus_bio_n',0):,}")
except Exception as e:
    st.warning(f"Could not load registry stats: {e}")

st.markdown("---")

# What's in the registry
st.markdown("### What's in the registry")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        f"""
        <div style='background:#F2F4F8;border-left:4px solid {NAVY};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>NHANES 2001-2018</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                44,898 adults - 9 cycles - PhenoAge + KDM computed<br>
                <strong>Finding:</strong> U.S. adults aged 40-60 are aging 6.8 years faster biologically than in 2009.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {GOLD};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS 2016 Venous Blood Study</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                9,567 adults 50+ - PhenoAge from real venous blood biomarkers<br>
                <strong>Finding:</strong> Highest biological age quintile is nearly 2x as likely to be cognitively impaired (27.9% vs 14.2%).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {TEAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS DBS Longitudinal (2006-2016)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                22,378 unique respondents - 6 waves - HbA1c, CRP, cholesterol, HDL, cystatin-C<br>
                Enables longitudinal biomarker trajectory analysis.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {NAVY};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>MIDUS (M2 + Refresher 1 + M3, 2004-2022)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                2,865 biomarker observations across 3 waves + 3,291 M3 cognitive (BTACT) - KDM bioage with within-MIDUS reference parameters<br>
                Distinctive for the registry: 9-marker inflammation panel (CRP, IL-6/8/10, TNF-alpha, fibrinogen, sICAM, sE-selectin, sUPAR), neuroendocrine (DHEA-S, IGF-1, urinary cortisol/catecholamines), bone turnover.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div style='background:#F2F4F8;border-left:4px solid {TEAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS Epigenetic Clocks</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                4,018 respondents - GrimAge2 + DunedinPACE (methylation-based)<br>
                Enables direct comparison of clinical biomarker vs. epigenetic clock approaches.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {CORAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS Pace of Aging (DunedinPACE)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                13,358 respondents - Balachandran et al. 2025, Nature Aging<br>
                Mean DunedinPACE: 1.49 years per calendar year (population average = 1.0).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {GOLD};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>BRFSS 2024 - Market Intelligence</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                457,670 U.S. adults - State and metro-level longevity market scoring<br>
                Identifies where INEXION-aligned consumer demand is strongest (DC corridor, MA, NH, UT, CO).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid #6B6B8D;
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>Incoming</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                UK Biobank (application in progress) - All of Us NIH (Anant, Tier 2 pending) -
                MIDUS CMS-linked restricted tier (Anant) - AgelessRx + Healthspan (DUA in review)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown("### What you can do")

left, right = st.columns(2)
with left:
    st.markdown(
        "**NHANES Explorer** - filter the 44,898-person NHANES cohort by age, sex, "
        "race, BMI, and biomarker values. See live counts, descriptive summaries, "
        "cycle trends, and export cohort slices as CSV.\n\n"
        "**HRS Explorer** - explore venous blood PhenoAge scores, epigenetic clocks, "
        "longitudinal DBS biomarker trends (2006-2016), cognitive outcomes, "
        "and functional status across five tabs.\n\n"
        "**MIDUS Explorer** - inflammation-panel-first cohort view across 3 biomarker "
        "waves (2004-2022). Tabs: Overview, Inflammation Panel, Cardiometabolic, "
        "Neuroendocrine, Wave Comparison, Cognition (M3 BTACT)."
    )
with right:
    st.markdown(
        "**Patient Analysis** - upload a PDF lab report once (or enter values manually) "
        "and explore the same patient across three views: PhenoAge biological age + "
        "10-year mortality risk, normative percentile vs. the U.S. population for their "
        "age-sex group, and intervention simulation showing which biomarker moves the "
        "needle most.\n\n"
        "**Validation Dashboard** - every clock the registry exposes tested against "
        "linked mortality from its source cohort. Cox proportional hazards, "
        "Kaplan-Meier survival curves, and concordance-index head-to-head between "
        "PhenoAge, KDM, GrimAge2, and DunedinPACE.\n\n"
        "**Research Workbench** - no-code hypothesis testing across NHANES, HRS, and MIDUS. "
        "Partial correlations, OLS regression, and scatter plots.\n\n"
        "**Dataset Catalog** - full inventory of what's loaded, what's pending "
        "access, and what's incoming. **Variable Dictionary** - definitions, units, "
        "and groupings for all registry variables."
    )

st.markdown("---")
st.caption(
    "All source data is de-identified. No PHI is present. "
    "NHANES: CDC public-use files. HRS: University of Michigan / NIA restricted access under RDA. "
    "MIDUS: ICPSR public-use files (CMS-linked restricted tier in progress). "
    "Prototype build - auth, audit logging, and remote object storage added in deployment phase."
)
