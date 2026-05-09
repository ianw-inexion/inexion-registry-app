"""
INEXION Longevity Registry — app entry point.
"""
from dotenv import load_dotenv
load_dotenv()

# ── Streamlit Cloud: load secrets into environment ────────────────────────────
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
from src.config import (
    APP_TITLE, APP_VERSION, NAVY, GOLD, TEAL, CORAL,
    NHANES_PARQUET, HRS_VBS_PARQUET, HRS_DBS_PARQUET,
    HRS_EPIGEN_PARQUET, HRS_POA_PARQUET, HRS_PUBLIC_PARQUET,
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
            HORAL — Healthspan Outcomes Registry for Active Longevity &nbsp;·&nbsp; v{APP_VERSION}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"**INEXION Registry**")
    st.caption(f"v{APP_VERSION}")
    st.markdown("---")
    st.markdown(
        "**Navigation**\n\n"
        "- NHANES Explorer\n"
        "- HRS Explorer\n"
        "- Biological Age Calculator\n"
        "- Normative Reference\n"
        "- Intervention Simulator\n"
        "- Research Workbench\n"
        "- Dataset Catalog\n"
        "- Variable Dictionary\n"
        "- Admin"
    )
    st.markdown("---")
    st.caption("Prototype build — local auth, no PHI.")

# ── Registry-wide stats ───────────────────────────────────────────────────────
datasets = {
    "NHANES": (NHANES_PARQUET, "n_total"),
    "HRS VBS": (HRS_VBS_PARQUET, None),
    "HRS DBS": (HRS_DBS_PARQUET, None),
    "HRS Clocks": (HRS_EPIGEN_PARQUET, None),
    "HRS PoA": (HRS_POA_PARQUET, None),
    "HRS Survey": (HRS_PUBLIC_PARQUET, None),
}

@st.cache_data
def get_registry_stats():
    stats = {}
    total_participants = 0

    if NHANES_PARQUET.exists():
        df = pd.read_parquet(NHANES_PARQUET, columns=['seqn'])
        stats['nhanes_n'] = len(df)
        total_participants += len(df)

    if HRS_VBS_PARQUET.exists():
        df = pd.read_parquet(HRS_VBS_PARQUET, columns=['hhidpn'])
        stats['hrs_vbs_n'] = len(df)
        total_participants += len(df)

    if HRS_DBS_PARQUET.exists():
        df = pd.read_parquet(HRS_DBS_PARQUET, columns=['hhidpn'])
        stats['hrs_dbs_n'] = df['hhidpn'].nunique()
        stats['hrs_dbs_obs'] = len(df)

    if HRS_EPIGEN_PARQUET.exists():
        df = pd.read_parquet(HRS_EPIGEN_PARQUET, columns=['hhidpn'])
        stats['hrs_epi_n'] = len(df)

    if HRS_POA_PARQUET.exists():
        df = pd.read_parquet(HRS_POA_PARQUET, columns=['hhidpn'])
        stats['hrs_poa_n'] = len(df)

    stats['total_observations'] = (
        stats.get('nhanes_n', 0) +
        stats.get('hrs_vbs_n', 0) +
        stats.get('hrs_dbs_obs', 0) +
        stats.get('hrs_epi_n', 0) +
        stats.get('hrs_poa_n', 0)
    )
    stats['datasets_loaded'] = sum(1 for k in ['nhanes_n','hrs_vbs_n','hrs_dbs_n','hrs_epi_n','hrs_poa_n'] if k in stats)
    return stats

try:
    s = get_registry_stats()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Datasets loaded", s.get('datasets_loaded', 0))
    c2.metric("NHANES participants", f"{s.get('nhanes_n',0):,}")
    c3.metric("HRS VBS (PhenoAge)", f"{s.get('hrs_vbs_n',0):,}")
    c4.metric("HRS DBS respondents", f"{s.get('hrs_dbs_n',0):,}")
    c5.metric("HRS DunedinPACE", f"{s.get('hrs_poa_n',0):,}")
except Exception as e:
    st.warning(f"Could not load registry stats: {e}")

st.markdown("---")

# ── What's in the registry ────────────────────────────────────────────────────
st.markdown("### What's in the registry")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        f"""
        <div style='background:#F2F4F8;border-left:4px solid {NAVY};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>NHANES 2001–2018</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                44,898 adults · 9 cycles · PhenoAge + KDM computed<br>
                <strong>Finding:</strong> U.S. adults aged 40–60 are aging 6.8 years faster biologically than in 2009.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {GOLD};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS 2016 Venous Blood Study</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                9,567 adults 50+ · PhenoAge from real venous blood biomarkers<br>
                <strong>Finding:</strong> Highest biological age quintile is nearly 2× as likely to be cognitively impaired (27.9% vs 14.2%).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {TEAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS DBS Longitudinal (2006–2016)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                22,378 unique respondents · 6 waves · HbA1c, CRP, cholesterol, HDL, cystatin-C<br>
                Enables longitudinal biomarker trajectory analysis.
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
                4,018 respondents · GrimAge2 + DunedinPACE (methylation-based)<br>
                Enables direct comparison of clinical biomarker vs. epigenetic clock approaches.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {CORAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS Pace of Aging (DunedinPACE)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                13,358 respondents · Balachandran et al. 2025, Nature Aging<br>
                Mean DunedinPACE: 1.49 years per calendar year (population average = 1.0).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid #6B6B8D;
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>Incoming</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                UK Biobank (application in progress) · All of Us NIH (Anant, Tier 2 pending) ·
                MIDUS (Anant, DUA pending) · AgelessRx + Healthspan (DUA in review)
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
        "**NHANES Explorer** — filter the 44,898-person NHANES cohort by age, sex, "
        "race, BMI, and biomarker values. See live counts, descriptive summaries, "
        "cycle trends, and export cohort slices as CSV.\n\n"
        "**HRS Explorer** — explore venous blood PhenoAge scores, epigenetic clocks, "
        "longitudinal DBS biomarker trends (2006–2016), cognitive outcomes, "
        "and functional status across five tabs."
    )
with right:
    st.markdown(
        "**Biological Age Calculator** — enter any patient's 9 standard lab values "
        "(or upload a PDF lab report) to compute PhenoAge and biological age delta.\n\n"
        "**Dataset Catalog** — full inventory of what's loaded, what's pending "
        "access, and what's incoming. **Variable Dictionary** — definitions, units, "
        "and groupings for all registry variables."
    )

st.markdown("---")
st.caption(
    "All source data is de-identified. No PHI is present. "
    "NHANES: CDC public-use files. HRS: University of Michigan / NIA restricted access under RDA. "
    "Prototype build — auth, audit logging, and remote object storage added in deployment phase."
)
