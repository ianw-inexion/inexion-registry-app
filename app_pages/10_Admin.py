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
    NSHAP_BIO_PARQUET, NSHAP_SOCIAL_PARQUET, NSHAP_CODEBOOK_PARQUET,
    BRFSS_STATE_PARQUET, BRFSS_METRO_PARQUET,
    GEO_CATALOG_PARQUET, GEO_DATASET_DIR,
    NHANES_MORTALITY_PARQUET, HRS_MORTALITY_PARQUET, MIDUS_MORTALITY_PARQUET,
    data_exists,
)
import pandas as pd
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
    ("NHANES Linked Mortality (LMF 2019)",   NHANES_MORTALITY_PARQUET,"NHANES"),
    ("HRS 2016 VBS - PhenoAge",              HRS_VBS_PARQUET,         "HRS"),
    ("HRS 2016 Public Survey",               HRS_PUBLIC_PARQUET,      "HRS"),
    ("HRS DBS Longitudinal (2006-2016)",     HRS_DBS_PARQUET,         "HRS"),
    ("HRS Epigenetic Clocks",                HRS_EPIGEN_PARQUET,      "HRS"),
    ("HRS Pace of Aging (DunedinPACE)",      HRS_POA_PARQUET,         "HRS"),
    ("HRS RAND mortality (death dates)",     HRS_MORTALITY_PARQUET,   "HRS"),
    ("MIDUS NDI mortality (37237 + 38024)",  MIDUS_MORTALITY_PARQUET, "MIDUS"),
    ("MIDUS Biomarker (M2 + R1 + M3)",       MIDUS_BIO_PARQUET,       "MIDUS"),
    ("MIDUS 3 Cognitive (BTACT)",            MIDUS_COG_PARQUET,       "MIDUS"),
    ("MIDUS variable codebook",              MIDUS_CODEBOOK_PARQUET,  "MIDUS"),
    ("NSHAP Biomarker (R1 + R2 + R3)",       NSHAP_BIO_PARQUET,       "NSHAP"),
    ("NSHAP Social / Sensory / Cognition",   NSHAP_SOCIAL_PARQUET,    "NSHAP"),
    ("NSHAP variable codebook",              NSHAP_CODEBOOK_PARQUET,  "NSHAP"),
    ("BRFSS state market scores (2024)",     BRFSS_STATE_PARQUET,     "BRFSS"),
    ("BRFSS metro market scores (2024)",     BRFSS_METRO_PARQUET,     "BRFSS"),
    ("GEO catalog summary (15 datasets)",    GEO_CATALOG_PARQUET,     "GEO"),
    ("GEO per-dataset bundle directory",     GEO_DATASET_DIR,         "GEO"),
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
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", f"{int(stats['n_total']):,}")
    c2.metric("With PhenoAge", f"{int(stats['n_with_phenoage']):,}")
    c3.metric("Cycles", f"{int(stats['n_cycles'])}")
except Exception as _e:
    st.warning(f"Coverage error: {_e}")

# Mortality outcome coverage
st.markdown("---")
st.markdown("### Mortality Outcome Coverage")
try:
    import pyarrow.parquet as _pq
    def _summ(label, path, time_col, event_col):
        if not data_exists(path):
            return {"Cohort": label, "n": "missing", "events": "-", "Median follow-up (yr)": "-"}
        df = pd.read_parquet(path, columns=[time_col, event_col])
        n = len(df)
        events = int(df[event_col].sum()) if event_col in df.columns else 0
        med = df[time_col].median() if time_col in df.columns else float('nan')
        return {"Cohort": label, "n": f"{n:,}", "events": f"{events:,}",
                "Median follow-up (yr)": f"{med:.1f}" if pd.notna(med) else "-"}

    mort_rows = []
    if data_exists(NHANES_MORTALITY_PARQUET):
        mort_rows.append(_summ("NHANES + LMF",        NHANES_MORTALITY_PARQUET,
                                "years_int_to_event", "mortality_status"))
    if data_exists(MIDUS_MORTALITY_PARQUET):
        mort_rows.append(_summ("MIDUS Biomarker (NDI 37237 + 38024)",
                                MIDUS_MORTALITY_PARQUET, "years_to_event", "mortality_status"))

    st.dataframe(pd.DataFrame(mort_rows), width="stretch", hide_index=True)
    st.caption(
        "NHANES mortality from CDC Linked Mortality File (LMF) 1999-2019. "
        "HRS mortality from RAND HRS Longitudinal File 1992-2022 (death year + month). "
        "MIDUS NDI (ICPSR 37237 Core + 38024 Refresher 1) is public download. "
        "NSHAP R3 deceased flag in nshap_mortality.parquet (binary - no follow-up time)."
    )
except Exception as _e:
    st.error(f"Mortality coverage error: {_e}")

# App inventory
st.markdown("---")
st.markdown("### App Pages")

PAGES = [
    ("1. NHANES Explorer",            "Filter 44,898-person NHANES cohort - Cohort builder - Biomarker trends - CSV export"),
    ("2. HRS Explorer",               "VBS PhenoAge - Clock comparison - DBS longitudinal biomarker trends - Health & function - Demographics"),
    ("3. MIDUS Explorer",             "3 biomarker waves (2004-2022, n=2,865) + M3 cognitive (n=3,291) - 9-marker inflammation panel - Cardiometabolic - Neuroendocrine - KDM bioage - Wave comparison"),
    ("3. Market Intelligence",        "BRFSS 2024 state and metro longevity market scoring (n=457,670)"),
    ("3c. NSHAP Explorer",            "NSHAP R1+R2+R3 (2005-2016, n=10,578 stacked obs) - DBS biomarkers (R1+R2: HbA1c/CRP/EBV/hemoglobin) - in-home social network roster - sensory measures (smell/hearing/peak flow) - MoCA cognition - timed gait - R3 biomarkers pending separate ICPSR release"),
    ("4. Patient Analysis",           "Single lab upload (or manual entry) feeds 6 tabs: Biological Age (PhenoAge + 10-yr mortality), Normative Reference (percentile vs. NHANES age-sex-race), PhenoAge Intervention, Metabolic Age, Liver Age, Kidney Age (NHANES-trained organ clocks)"),
    ("5. Validation",                 "Cox PH + Kaplan-Meier + concordance index for every clock against linked mortality - NHANES PhenoAge, HRS VBS PhenoAge, MIDUS KDM, and HRS clock head-to-head (PhenoAge vs GrimAge2 vs DunedinPACE)"),
    ("6. Organ Ages",                 "Phase 4 - Inflammation / Liver / Kidney / Metabolic age clocks; mortality validation Cox HRs per organ; cross-clock correlation"),
    ("6b. Methylation Clocks",        "Phase 6 v0 - GrimAge2, DunedinPACE methyl + behavioral (HRS), DNAm-imputed CRP/HbA1c, top-quintile concordance, UKB roadmap"),
    ("7. Research Workbench",         "No-code hypothesis testing - 5 model types (OLS / Cox PH / Logistic / Mixed-effects / GAM) - BH-FDR session log - NHANES + HRS + HRS DBS + MIDUS + NSHAP"),
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
    ("OK",      "All parquets uploaded to S3",       "temp_Ian_Nirav/staging/ - NHANES + all HRS + MIDUS + NSHAP - May 2026"),
    ("OK",      "AWS billing alert",                 "$200/month CloudWatch alarm -> ianw@inexion.com"),
    ("OK",      "IAM users created",                 "ian_wendt (admin + billing) - nirav_vira (admin)"),
    ("OK",      "MIDUS public ICPSR ingested",       "M2 + Refresher 1 + M3 biomarker + M3 BTACT cognitive - 2,865 + 3,291 obs"),
    ("OK",      "NSHAP R1+R2+R3 ingested (public-use)","ICPSR 20541/34921/36873 via pyreadr - 10,578 stacked obs - biomarkers + social + R3 mortality"),
    ("Pending", "NSHAP R3 biomeasures release",      "Open ICPSR/NORC inquiry - DBS assays not present in 36873 public or restricted; brief drafted for Anant"),
    ("Pending", "NSHAP R4 (2021-23)",                "ICPSR 39511 - restricted-only, IRB pending"),
    ("OK",      "GEO molecular reference catalog",   "15 curated transcriptomics datasets ingested - ~2,500 samples - blood + muscle + fibroblast + multi-tissue"),
    ("OK",      "GEO expression layer",              "12 of 15 expression matrices recoverable: 9 GEO suppl + 1 Zenodo (GSE248822) + 2 Allen Atlas (GSE271896, GSE275067)"),
    ("Pending", "GSE216842 expression",              "Email drafted to Yu Sun lab; per-sample _RAW.tar only on GEO"),
    ("Pending", "GSE280110 + GSE226189 expression",  "_RAW.tar only on GEO; would require local re-alignment - low priority"),
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
