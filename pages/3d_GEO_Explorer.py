"""
GEO Explorer - INEXION molecular-aging reference catalog.

Surfaces the 15 curated NCBI GEO transcriptomics datasets that form the
registry's molecular-aging signature layer. Catalog overview at the top,
then per-dataset drill-in with series info, sample metadata, and
demographic distributions.

Datasets that ship analysis-ready expression tables (8/15) get a sample-
gene matrix preview; the others show metadata only because the GEO
submitter only deposited per-sample raw files.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import (
    NAVY, GOLD, CORAL, TEAL, LIGHT_BG,
    GEO_CATALOG_PARQUET, GEO_DATASET_DIR,
    data_exists, IS_S3,
)

st.set_page_config(page_title="GEO Explorer - INEXION Registry", layout="wide")

# Header
st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            GEO Explorer</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Curated molecular-aging transcriptomics catalog &middot; 15 datasets &middot;
            ~2,500 samples &middot; blood, muscle, fibroblast, multi-tissue
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _load_catalog() -> pd.DataFrame:
    """Load the catalog summary parquet."""
    if not data_exists(GEO_CATALOG_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(GEO_CATALOG_PARQUET)


@st.cache_data(show_spinner=False)
def _load_metadata(accession: str) -> pd.DataFrame:
    """Load per-accession sample metadata parquet."""
    path = (
        f"{str(GEO_DATASET_DIR).rstrip('/')}/{accession}/metadata.parquet"
        if IS_S3 else
        Path(GEO_DATASET_DIR) / accession / "metadata.parquet"
    )
    if not data_exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def _load_series_info(accession: str) -> dict:
    """Load per-accession series-level info JSON."""
    if IS_S3:
        try:
            import s3fs
            fs = s3fs.S3FileSystem(anon=False)
            path = f"{str(GEO_DATASET_DIR).rstrip('/')}/{accession}/series_info.json"
            with fs.open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    path = Path(GEO_DATASET_DIR) / accession / "series_info.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def _load_expression_preview(accession: str, n_genes: int = 50) -> pd.DataFrame:
    """Load the first N genes of the expression matrix as a preview.
    Returns empty DataFrame if expression isn't on disk."""
    path = (
        f"{str(GEO_DATASET_DIR).rstrip('/')}/{accession}/expression.parquet"
        if IS_S3 else
        Path(GEO_DATASET_DIR) / accession / "expression.parquet"
    )
    if not data_exists(path):
        return pd.DataFrame()
    df = pd.read_parquet(path)
    return df.iloc[:, :n_genes]


catalog = _load_catalog()
if catalog.empty:
    st.warning(
        "GEO catalog summary parquet is not available. Run "
        "`python build_geo_parquet.py` from the pipeline directory and "
        "deploy data with `scripts/deploy.ps1`."
    )
    st.stop()


# ---- Catalog overview ----
st.markdown("### Catalog Overview")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Datasets", len(catalog))
with c2:
    st.metric("Total samples", f"{int(catalog['n_samples'].sum()):,}")
with c3:
    st.metric("With expression matrix",
                 f"{int(catalog['has_expression'].sum())} / {len(catalog)}")
with c4:
    n_rnaseq = (catalog["platform"].str.contains("RNA", case=False, na=False)).sum()
    st.metric("RNA-seq",
                 f"{n_rnaseq} / {len(catalog)}",
                 help="Remainder are microarray (Illumina/Affymetrix).")

# Sortable catalog table
display_cols = [
    "accession", "priority", "category", "platform", "year",
    "n_samples", "n_genes", "has_expression",
    "age_min", "age_max", "n_male", "n_female", "title",
]
existing = [c for c in display_cols if c in catalog.columns]
st.dataframe(
    catalog[existing].rename(columns={
        "accession":      "Accession",
        "priority":       "Priority",
        "category":       "Category",
        "platform":       "Platform",
        "year":           "Year",
        "n_samples":      "Samples",
        "n_genes":        "Genes",
        "has_expression": "Has Expr",
        "age_min":        "Age min",
        "age_max":        "Age max",
        "n_male":         "Male",
        "n_female":       "Female",
        "title":          "Title",
    }),
    use_container_width=True, hide_index=True, height=480,
)


# ---- Per-dataset drill-in ----
st.markdown("### Inspect a Dataset")

acc_choice = st.selectbox(
    "Choose an accession",
    options=catalog["accession"].tolist(),
    format_func=lambda a: f"{a} - {catalog.loc[catalog.accession == a, 'title'].iloc[0][:80]}"
                          if a in catalog["accession"].values else a,
)

if not acc_choice:
    st.stop()

cat_row = catalog[catalog["accession"] == acc_choice].iloc[0]
series_info = _load_series_info(acc_choice)
metadata = _load_metadata(acc_choice)


# Series info card
st.markdown(
    f"""
    <div style='background:{LIGHT_BG};border-left:5px solid {NAVY};
                padding:16px 20px;border-radius:6px;margin:12px 0;'>
    <div style='color:{GOLD};font-size:11px;letter-spacing:1.5px;
                font-weight:600;text-transform:uppercase;'>
        {cat_row.priority or '—'} &middot; {cat_row.category or '—'} &middot;
        {cat_row.platform or '—'} &middot; {cat_row.year or '—'}
    </div>
    <div style='color:{NAVY};font-size:18px;font-weight:700;margin:6px 0;'>
        {acc_choice}: {(series_info.get('title', '') or cat_row.title)[:140]}
    </div>
    <div style='color:#1A1A2E;font-size:13px;line-height:1.55;'>
        {(series_info.get('summary', '') or '')[:600]}
    </div>
    <div style='color:#6B7280;font-size:12px;margin-top:8px;'>
        <a href='{cat_row.geo_url}' target='_blank' style='color:{NAVY};
            text-decoration:none;font-weight:600;'>
            View on NCBI GEO &rarr;</a>
    </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if cat_row.inexion_relevance:
    st.markdown(
        f"<div style='background:rgba(201,148,26,0.08);border-left:3px solid {GOLD};"
        f"padding:10px 16px;border-radius:4px;margin:12px 0;font-size:13px;'>"
        f"<b>INEXION relevance:</b> {cat_row.inexion_relevance}</div>",
        unsafe_allow_html=True,
    )

# Metric strip
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Samples", cat_row.n_samples)
with m2:
    if cat_row.n_genes and cat_row.n_genes > 0:
        st.metric("Genes / probes", f"{int(cat_row.n_genes):,}")
    else:
        st.metric("Genes / probes", "—",
                    help="Expression matrix not deposited as analysis-ready "
                         "table; only per-sample raw files in _RAW.tar.")
with m3:
    if pd.notna(cat_row.age_min) and pd.notna(cat_row.age_max):
        st.metric("Age range",
                     f"{int(cat_row.age_min)}-{int(cat_row.age_max)}",
                     help=f"Mean {cat_row.age_mean:.1f}"
                           if pd.notna(cat_row.age_mean) else None)
    else:
        st.metric("Age range", "—",
                    help="Age not parsed from sample characteristics.")
with m4:
    if cat_row.n_male + cat_row.n_female > 0:
        st.metric("Sex split (M / F)",
                     f"{cat_row.n_male} / {cat_row.n_female}")
    else:
        st.metric("Sex split", "—")


# ---- Demographic plots ----
if not metadata.empty:
    plot_tabs = st.tabs(["Age distribution", "Sex breakdown",
                         "Tissue / cell type", "Sample metadata table"])

    with plot_tabs[0]:
        if "age" in metadata.columns and metadata["age"].notna().any():
            fig = px.histogram(
                metadata.dropna(subset=["age"]),
                x="age", nbins=20,
                color_discrete_sequence=[NAVY],
            )
            fig.update_layout(
                title="Age distribution",
                xaxis_title="Age (years)", yaxis_title="Sample count",
                height=380, plot_bgcolor="white", showlegend=False,
            )
            fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
            fig.update_yaxes(showgrid=True, gridcolor="#E5E7EB")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Age not available in this dataset's sample metadata.")

    with plot_tabs[1]:
        if "sex" in metadata.columns and metadata["sex"].notna().any():
            sex_counts = metadata["sex"].value_counts().reset_index()
            sex_counts.columns = ["Sex", "Count"]
            fig = px.bar(
                sex_counts, x="Sex", y="Count",
                color="Sex",
                color_discrete_map={"Male": NAVY, "Female": CORAL},
            )
            fig.update_layout(
                height=360, plot_bgcolor="white", showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sex not available in this dataset's sample metadata.")

    with plot_tabs[2]:
        for col in ("tissue", "cell_type", "treatment"):
            if col in metadata.columns and metadata[col].notna().any():
                counts = metadata[col].dropna().value_counts().head(20)
                fig = px.bar(
                    x=counts.values, y=counts.index, orientation="h",
                    color_discrete_sequence=[TEAL],
                )
                fig.update_layout(
                    title=col.replace("_", " ").title() + " (top 20)",
                    xaxis_title="Sample count", yaxis_title="",
                    height=400, plot_bgcolor="white", showlegend=False,
                    margin=dict(l=80),
                )
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)

    with plot_tabs[3]:
        st.caption(
            f"Full sample metadata for {acc_choice}. Each row is one GSM "
            "sample; columns are characteristics extracted from the GEO "
            "Series Matrix headers."
        )
        # Drop the verbose raw column for display
        meta_display = metadata.drop(columns=["characteristics_raw"], errors="ignore")
        st.dataframe(
            meta_display, use_container_width=True, height=420,
        )


# ---- Expression preview ----
if cat_row.has_expression:
    st.markdown("#### Expression Matrix Preview")
    st.caption(
        f"First 50 of {int(cat_row.n_genes):,} genes/probes for "
        f"{cat_row.n_samples} samples. Full matrix loadable via "
        "`load_with_expression()` in inexion_registry.geo."
    )
    expr = _load_expression_preview(acc_choice, n_genes=50)
    if not expr.empty:
        st.dataframe(expr, use_container_width=True, height=320)
    else:
        st.info("Expression preview not available.")
else:
    st.markdown("#### Expression Matrix")
    st.warning(
        f"{acc_choice} did not deposit an analysis-ready expression table in "
        "GEO's /suppl/ directory; only per-sample raw files (FASTQ links / "
        "CEL files) are available via `<accession>_RAW.tar`. To get expression, "
        "either (a) untar and process the per-sample files locally, or (b) "
        "look for an aggregated count matrix on the paper's GitHub or "
        "supplementary materials."
    )
