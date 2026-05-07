"""
Admin — data freshness, pipeline status, QC. Internal-only in production.
"""
from pathlib import Path
import datetime as dt
import streamlit as st
from src.config import NHANES_PARQUET, NHANES_HARMONIZED, HEADLINE_DIR, NAVY, GOLD
from src import data

st.set_page_config(page_title="Admin — INEXION Registry", layout="wide")
st.title("Admin")
st.caption("Pipeline health, data freshness, QC. Restricted to internal role in production.")


def file_stat(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    s = path.stat()
    return {
        "exists": True,
        "size_mb": s.st_size / 1024 / 1024,
        "modified": dt.datetime.fromtimestamp(s.st_mtime),
    }

st.markdown("### Data artifacts")
files = [
    ("NHANES harmonized (all cycles)", NHANES_HARMONIZED),
    ("NHANES with PhenoAge + KDM",      NHANES_PARQUET),
    ("Headline analyses directory",      HEADLINE_DIR),
]
for label, path in files:
    info = file_stat(path)
    if not info["exists"]:
        st.error(f"**{label}** — missing at `{path}`")
        continue
    c1, c2, c3 = st.columns([3, 1, 2])
    c1.markdown(f"**{label}**  \n`{path}`")
    if path.is_file():
        c2.metric("Size", f"{info['size_mb']:.1f} MB")
    else:
        c2.metric("Type", "Directory")
    age_days = (dt.datetime.now() - info["modified"]).days
    c3.metric("Last modified", info["modified"].strftime("%Y-%m-%d"),
              delta=f"{age_days} days ago")

st.markdown("### Coverage snapshot")
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
    c4.metric("Cycle range",
              f"{int(stats['min_year'])}–{int(stats['max_year'])}")
except Exception as e:
    st.error(f"Coverage query failed: {e}")

st.markdown("### To be added in v0.3 (deployed)")
st.markdown(
    "- Supabase auth-wall with Google SSO (`@inexion.com`) + magic-link invite\n"
    "- Audit log: every cohort query + export recorded to `registry_audit`\n"
    "- Pipeline-run health (last NHANES sync, last HRS merge, failures)\n"
    "- Data freshness SLO: NHANES refresh quarterly, HRS semi-annually\n"
    "- QC dashboard: missingness per biomarker, outlier counts, PhenoAge r vs. age\n"
    "- User management: invite, revoke, role changes"
)
