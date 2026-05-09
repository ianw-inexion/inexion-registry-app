"""
Admin - data freshness, pipeline health, registry status. Internal only.
"""
from pathlib import Path
import datetime as dt
import streamlit as st
from src.config import (
    NHANES_PARQUET, NHANES_HARMONIZED, HEADLINE_DIR, NAVY, GOLD,
    HRS_VBS_PARQUET, HRS_PUBLIC_PARQUET, HRS_DBS_PARQUET,
    HRS_EPIGEN_PARQUET, HRS_POA_PARQUET,
    MIDUS_BIO_PARQUET, MIDUS_COG_PARQUET, MIDUS_CODEBOOK_PARQUET,
    BRFSS_STATE_PARQUET, BRFSS_METRO_PARQUET,
)
from src import data

st.set_page_config(page_title="Admin - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>Admin</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Pipeline health - Data freshness - Registry status - Internal only
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def file_stat(path) -> dict:
    from src.config import IS_S3, data_exists
    if IS_S3:
        # For S3 paths just report as present - size/date not critical in cloud
        exists = data_exists(path)
        return {"exists": exists, "size_mb": None, "modified": None}
    path = Path(path)
    if not path.exists():
        return {"exists": False}
    s = path.stat()
    return {
        "exists": True,
        "size_mb": s.st_size / (1024 * 1024),
        "modified": dt.datetime.fromtimestamp(s.st_mtime),
    }


# Data artifacts
st.markdown("### Registry Data Files")

ALL_FILES = [
    ("NHANES harmonized (all cycles)",       NHANES_HARMONIZED,       "NHANES"),
    ("NHANES with PhenoAge + KDM",           NHANES_PARQUET,          "NHANES"),
    ("HRS 2016 VBS - PhenoAge",              HRS_VBS_PARQUET,         "HRS"),
    ("HRS 2016 Public Survey",               HRS_PUBLIC_PARQUET,      "HRS"),
    ("HRS DBS Longitudinal (2006-2016)",     HRS_DBS_PARQUET,         "HRS"),
    ("HRS Epigenetic Clocks",                HRS_EPIGEN_PARQUET,      "HRS"),
    ("HRS Pace of Aging (DunedinPACE)",      HRS_POA_PARQUET,         "HRS"),
    ("MIDUS Biomarker (M2 + R1 + M3)",       MIDUS_BIO_PARQUET,       "MIDUS"),
    ("MIDUS 3 Cognitive (BTACT)",            MIDUS_COG_PARQUET,       "MIDUS"),
    ("MIDUS variable codebook",              MIDUS_CODEBOOK_PARQUET,  "MIDUS"),
    ("BRFSS state market scores (2024)",     BRFSS_STATE_PARQUET,     "BRFSS"),
    ("BRFSS metro market scores (2024)",     BRFSS_METRO_PARQUET,     "BRFSS"),
    ("Headline analyses directory",          HEADLINE_DIR,            "Analyses"),
]

current_group = None
for label, path, group in ALL_FILES:
    if group != current_group:
        st.markdown(f"**{group}**")
        current_group = group
    info = file_stat(path)
    if not info["exists"]:
        st.error(f"  {label} - missing at `{Path(str(path)).name}`")
        continue
    c1, c2, c3 = st.columns([4, 1, 2])
    path_name = str(path).split("/")[-1]
    c1.markdown(f"  {label}  \n  `{path_name}`")
    if info['size_mb'] is not None:
        c2.metric("Size", f"{info['size_mb']:.1f} MB")
    else:
        c2.metric("Source", "S3")
    if info['modified'] is not None:
        age_days = (dt.datetime.now() - info["modified"]).days
        c3.metric("Last modified", info["modified"].strftime("%Y-%m-%d"),
                  delta=f"{age_days}d ago")
    else:
        c3.metric("Status", "In S3")

# NHANES coverage snapshot
st.markdown("---")
st.markdown("### NHANES Coverage Snapshot")
try:
    stats = data.dataset_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total rows", f"{int(stats['n_total']):,}")
    c2.metric("PhenoAge coverage",
              f"{int(stats['n_with_phenoage']):,}",
              delta=f"{100*stats['n_with_phenoage']/stats['n_total']:.1f}%")
    c3.metric("KDM coverage",
              f"{int(stats['n_with_kdm']):,}",
              delta=f"{100*stats['n_with_kdm']/stats['n_total']:.1f}%")
    c4.metric("Cycle range", f"{int(stats['min_year'])}-{int(stats['max_year'])}")
except Exception as e:
    st.error(f"Coverage query failed: {e}")

# App inventory
st.markdown("---")
st.markdown("### App Pages")

PAGES = [
    ("1. NHANES Explorer",            "Filter 44,898-person NHANES cohort - Cohort builder - Biomarker trends - CSV export"),
    ("2. HRS Explorer",               "VBS PhenoAge - Clock comparison - DBS longitudinal biomarker trends - Health & function - Demographics"),
    ("3. MIDUS Explorer",             "3 biomarker waves (2004-2022, n=2,865) + M3 cognitive (n=3,291) - 9-marker inflammation panel - Cardiometabolic - Neuroendocrine - KDM bioage - Wave comparison"),
    ("3. Market Intelligence",        "BRFSS 2024 state and metro longevity market scoring (n=457,670)"),
    ("4. Patient Analysis",           "Single lab upload (or manual entry) feeds 3 tabs: Biological Age (PhenoAge + 10-yr mortality), Normative Reference (percentile vs. NHANES age-sex), Intervention Simulator (biomarker contributions + what-if sliders)"),
    ("7. Research Workbench",         "No-code hypothesis testing - Partial correlations - OLS regression - Scatter plots - NHANES + HRS + MIDUS"),
    ("8. Dataset Catalog",            "Full inventory of all loaded, pending, and incoming datasets with access details"),
    ("9. Variable Dictionary",        "Definitions, units, and groupings for all registry variables"),
    ("10. Admin",                     "This page - pipeline health, data freshness, deployment status"),
]

for name, desc in PAGES:
    st.markdown(f"**{name}** - {desc}")

# Deployment status
st.markdown("---")
st.markdown("### Deployment Status")

status_items = [
    ("OK",      "S3 bucket provisioned",             "inexion-registry (us-east-2) - 4 zones: raw / curated / analytics / dev"),
    ("OK",      "All parquets uploaded to S3",       "temp_Ian_Nirav/staging/ - NHANES + all HRS datasets + MIDUS - May 2026"),
    ("OK",      "AWS billing alert",                 "$200/month CloudWatch alarm -> ianw@inexion.com"),
    ("OK",      "IAM users created",                 "ian_wendt (admin + billing) - nirav_vira (admin)"),
    ("OK",      "MIDUS public ICPSR ingested",       "M2 + Refresher 1 + M3 biomarker + M3 BTACT cognitive - 2,865 + 3,291 obs"),
    ("Pending", "AWS Glue catalog",                  "Pending Nirav - databases: inexion_raw / curated / analytics"),
    ("Pending", "Athena workgroups",                 "Pending Nirav - per-user spend limits"),
    ("Pending", "Auth (Google SSO + magic-link)",    "Pending - Supabase project + Railway deployment"),
    ("Pending", "registry.inexion.com",              "Pending - Vercel + Next.js public shell"),
    ("Pending", "All of Us Tier 2",                  "In progress - Anant driving application"),
    ("Pending", "MIDUS CMS-linked restricted tier",  "In progress - Anant driving (public ICPSR portion now ingested)"),
    ("Pending", "AgelessRx DUA",                     "Mark Burger reviewing - execution pending partner signature"),
    ("Pending", "Healthspan data activation",        "Q3 2026 target - LOI executed Feb 2026"),
    ("Pending", "HRS HCAP + APOE supplement",        "Pending additional HRS application - unlocks full H4 upgrade"),
    ("Pending", "UK Biobank access",                 "Application in progress - 3-6 month approval timeline"),
]

for icon, item, detail in status_items:
    if icon == "OK":
        prefix = ":white_check_mark:"
    else:
        prefix = ":hourglass_flowing_sand:"
    st.markdown(f"{prefix} **{item}** - {detail}")

st.markdown("---")
st.caption("INEXION Registry - Prototype v0.3 - Internal use only - No PHI present")
