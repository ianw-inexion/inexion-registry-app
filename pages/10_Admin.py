"""
Admin — data freshness, pipeline health, registry status. Internal only.
"""
from pathlib import Path
import datetime as dt
import streamlit as st
from src.config import (
    NHANES_PARQUET, NHANES_HARMONIZED, HEADLINE_DIR, NAVY, GOLD,
    HRS_VBS_PARQUET, HRS_PUBLIC_PARQUET, HRS_DBS_PARQUET,
    HRS_EPIGEN_PARQUET, HRS_POA_PARQUET,
)
from src import data

st.set_page_config(page_title="Admin — INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>Admin</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Pipeline health · Data freshness · Registry status · Internal only
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def file_stat(path) -> dict:
    from src.config import IS_S3, data_exists
    if IS_S3:
        # For S3 paths just report as present — size/date not critical in cloud
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


# ── Data artifacts ────────────────────────────────────────────────────────────
st.markdown("### Registry Data Files")

ALL_FILES = [
    ("NHANES harmonized (all cycles)",       NHANES_HARMONIZED,   "NHANES"),
    ("NHANES with PhenoAge + KDM",           NHANES_PARQUET,      "NHANES"),
    ("HRS 2016 VBS — PhenoAge",              HRS_VBS_PARQUET,     "HRS"),
    ("HRS 2016 Public Survey",               HRS_PUBLIC_PARQUET,  "HRS"),
    ("HRS DBS Longitudinal (2006–2016)",     HRS_DBS_PARQUET,     "HRS"),
    ("HRS Epigenetic Clocks",                HRS_EPIGEN_PARQUET,  "HRS"),
    ("HRS Pace of Aging (DunedinPACE)",      HRS_POA_PARQUET,     "HRS"),
    ("Headline analyses directory",          HEADLINE_DIR,        "Analyses"),
]

current_group = None
for label, path, group in ALL_FILES:
    if group != current_group:
        st.markdown(f"**{group}**")
        current_group = group
    info = file_stat(path)
    if not info["exists"]:
        st.error(f"  {label} — missing at `{path.name}`")
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
        c3.metric("Status", "✅ In S3")

# ── NHANES coverage snapshot ──────────────────────────────────────────────────
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
    c4.metric("Cycle range", f"{int(stats['min_year'])}–{int(stats['max_year'])}")
except Exception as e:
    st.error(f"Coverage query failed: {e}")

# ── App inventory ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### App Pages")

PAGES = [
    ("1. NHANES Explorer",            "Filter 44,898-person NHANES cohort · Cohort builder · Biomarker trends · CSV export"),
    ("2. HRS Explorer",               "VBS PhenoAge · Clock comparison · DBS longitudinal biomarker trends · Health & function · Demographics"),
    ("3. Biological Age Calculator",  "Enter 9 lab values or upload PDF lab report · Computes PhenoAge + delta + 10-yr mortality risk"),
    ("4. Normative Reference",        "Percentile lookup — where does a patient stand vs. the U.S. population for their age-sex group?"),
    ("5. Intervention Simulator",     "Biomarker contribution waterfall · Simulate treatment targets · Real-time PhenoAge update · PDF upload"),
    ("6. Research Workbench",         "No-code hypothesis testing · Partial correlations · OLS regression · Scatter plots · NHANES + HRS"),
    ("7. Dataset Catalog",            "Full inventory of all loaded, pending, and incoming datasets with access details"),
    ("8. Variable Dictionary",        "Definitions, units, and groupings for all registry variables"),
    ("9. Admin",                      "This page — pipeline health, data freshness, deployment status"),
]

for name, desc in PAGES:
    st.markdown(f"**{name}** — {desc}")

# ── Deployment status ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Deployment Status")

status_items = [
    ("✅", "S3 bucket provisioned",             "inexion-registry (us-east-2) · 4 zones: raw / curated / analytics / dev"),
    ("✅", "All parquets uploaded to S3",       "temp_Ian_Nirav/staging/ — NHANES + all HRS datasets · May 2026"),
    ("✅", "AWS billing alert",                 "$200/month CloudWatch alarm → ianw@inexion.com"),
    ("✅", "IAM users created",                 "ian_wendt (admin + billing) · nirav_vira (admin)"),
    ("⏳", "AWS Glue catalog",                  "Pending Nirav — databases: inexion_raw / curated / analytics"),
    ("⏳", "Athena workgroups",                 "Pending Nirav — per-user spend limits"),
    ("⏳", "Auth (Google SSO + magic-link)",    "Pending — Supabase project + Railway deployment"),
    ("⏳", "registry.inexion.com",              "Pending — Vercel + Next.js public shell"),
    ("⏳", "All of Us Tier 2",                  "In progress — Anant driving application"),
    ("⏳", "MIDUS ICPSR DUA",                   "In progress — Anant driving"),
    ("⏳", "AgelessRx DUA",                     "Mark Burger reviewing — execution pending partner signature"),
    ("⏳", "Healthspan data activation",        "Q3 2026 target — LOI executed Feb 2026"),
    ("⏳", "HRS HCAP + APOE supplement",        "Pending additional HRS application — unlocks full H4 upgrade"),
    ("⏳", "UK Biobank access",                 "Application in progress — 3–6 month approval timeline"),
]

for icon, item, detail in status_items:
    st.markdown(f"{icon} **{item}** — {detail}")

st.markdown("---")
st.caption("INEXION Registry — Prototype v0.3 · Internal use only · No PHI present")
