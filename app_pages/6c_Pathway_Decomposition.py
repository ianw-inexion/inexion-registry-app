"""
Pathway Decomposition - Primary aging vs Inflammation vs Disuse.

GSE242202 explicitly disentangles intrinsic muscle aging from secondary
drivers (chronic inflammation and physical inactivity). This page recreates
that decomposition using three canonical gene-pathway signature scores
computed on the dataset's expression matrix:

  Primary aging:     senescence + longevity-axis genes (CDKN2A, CDKN1A, GLB1,
                      GDF15, FOXO3, IGF1, SIRT1, SIRT3, LMNA, TERT)
  Chronic inflammation: NF-κB targets and SASP cytokines (IL6, TNF, IL1B,
                      NFKB1, CCL2, CXCL8, NLRP3, SERPINE1, PTGS2)
  Disuse / muscle atrophy: FOXO3-driven ubiquitin-proteasome (FBXO32,
                      TRIM63, MSTN, MAFBX) plus slow-vs-fast fiber markers
                      (MYH7, MYH2)

For each signature: log1p-transform raw counts, z-score per gene, signed
sum (up-with-pathway = +1, down-with-pathway = -1), then linear regression
against chronological age. The signature with the highest R² is the
strongest age-tracking pathway in this cohort - which the GSE242202 paper
argued was inflammation + disuse, not primary aging itself.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import (
    NAVY, GOLD, CORAL, TEAL, LIGHT_BG,
    GEO_CATALOG_PARQUET, GEO_DATASET_DIR,
    data_exists, IS_S3,
)

st.set_page_config(page_title="Pathway Decomposition - INEXION Registry", layout="wide")

# Header
st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Pathway Decomposition</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Primary aging vs chronic inflammation vs disuse / atrophy &middot;
            decomposed from GSE242202 muscle RNA-seq
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---- Pathway gene panels ----
# Each entry: gene_symbol -> (direction, ENSG_id). Direction +1 means
# expression rises when the pathway is active; -1 means it falls.

PRIMARY_AGING_PANEL = {
    # Senescence/SASP - rise with biological age
    "CDKN2A":  (+1, "ENSG00000147889"),  # p16
    "CDKN1A":  (+1, "ENSG00000124762"),  # p21
    "GLB1":    (+1, "ENSG00000170266"),  # β-gal
    "GDF15":   (+1, "ENSG00000130513"),
    "LMNA":    (+1, "ENSG00000160789"),  # premature-aging gene
    # Longevity / IGF axis - fall with biological age
    "FOXO3":   (-1, "ENSG00000118689"),
    "IGF1":    (-1, "ENSG00000017427"),
    "SIRT1":   (-1, "ENSG00000096717"),
    "SIRT3":   (-1, "ENSG00000142082"),
    "TERT":    (-1, "ENSG00000164362"),
}

INFLAMMATION_PANEL = {
    "IL6":      (+1, "ENSG00000136244"),
    "TNF":      (+1, "ENSG00000232810"),
    "IL1B":     (+1, "ENSG00000125538"),
    "NFKB1":    (+1, "ENSG00000109320"),
    "CCL2":     (+1, "ENSG00000108691"),
    "CXCL8":    (+1, "ENSG00000169429"),  # IL-8
    "NLRP3":    (+1, "ENSG00000162711"),
    "SERPINE1": (+1, "ENSG00000106366"),  # PAI-1
    "PTGS2":    (+1, "ENSG00000073756"),  # COX-2
    "CRP":      (+1, "ENSG00000132693"),
}

DISUSE_PANEL = {
    # FOXO3-driven ubiquitin-proteasome (muscle atrophy)
    "FBXO32":  (+1, "ENSG00000156804"),  # Atrogin-1
    "TRIM63":  (+1, "ENSG00000158022"),  # MuRF1
    "MSTN":    (+1, "ENSG00000138379"),  # myostatin
    # Slow/fast fiber rebalance under disuse - slow fibers (MYH7) drop
    "MYH7":    (-1, "ENSG00000092054"),
    "MYH2":    (+1, "ENSG00000125414"),  # fast fiber gain
    # Mitochondrial biogenesis collapses under disuse
    "PPARGC1A": (-1, "ENSG00000109819"),  # PGC-1α
}


# ---- Loaders ----
@st.cache_data(show_spinner=False)
def _load_geo_catalog():
    if not data_exists(GEO_CATALOG_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(GEO_CATALOG_PARQUET)


@st.cache_data(show_spinner=False)
def _load_geo_expression(accession: str) -> pd.DataFrame:
    path = (
        f"{str(GEO_DATASET_DIR).rstrip('/')}/{accession}/expression.parquet"
        if IS_S3 else
        Path(GEO_DATASET_DIR) / accession / "expression.parquet"
    )
    if not data_exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def _load_geo_metadata(accession: str) -> pd.DataFrame:
    path = (
        f"{str(GEO_DATASET_DIR).rstrip('/')}/{accession}/metadata.parquet"
        if IS_S3 else
        Path(GEO_DATASET_DIR) / accession / "metadata.parquet"
    )
    if not data_exists(path):
        return pd.DataFrame()
    return pd.read_parquet(path)


def _resolve_gene(expr_columns, symbol: str, ensg: str):
    """Match either the gene symbol or an ENSG ID (prefix-tolerant for
    Ensembl version suffixes like ENSG00000... .12)."""
    sym_upper = symbol.upper()
    ensg_upper = ensg.upper()
    for col in expr_columns:
        col_upper = str(col).upper()
        if col_upper == sym_upper:
            return col
        if col_upper == ensg_upper or col_upper.startswith(ensg_upper + "."):
            return col
    return None


def _compute_signature(expr_df, panel):
    """Returns (signature_series, n_resolved, resolved_symbols)."""
    cols = list(expr_df.columns)
    sig = pd.Series(0.0, index=expr_df.index)
    resolved = []
    for sym, (direction, ensg) in panel.items():
        col = _resolve_gene(cols, sym, ensg)
        if col is None:
            continue
        x = pd.to_numeric(expr_df[col], errors="coerce")
        x = np.log1p(x.clip(lower=0))
        sd = x.std(ddof=0)
        if sd == 0 or pd.isna(sd):
            continue
        z = (x - x.mean()) / sd
        sig = sig + direction * z
        resolved.append(sym)
    return sig, len(resolved), resolved


def _fit_vs_age(signature, ages):
    """OLS fit of signature ~ age. Returns dict with R², slope, intercept, p."""
    df = pd.DataFrame({"sig": signature.values, "age": ages.values}).dropna()
    if len(df) < 10:
        return None
    from scipy import stats as scistats
    slope, intercept, r, p, se = scistats.linregress(df["age"], df["sig"])
    return {
        "n":         len(df),
        "slope":     slope,
        "intercept": intercept,
        "r_squared": r ** 2,
        "p_value":   p,
        "se":        se,
        "df":        df,
    }


# ---- Page body ----
catalog = _load_geo_catalog()
if catalog.empty:
    st.warning(
        "GEO catalog parquet not available. Run "
        "`python build_geo_parquet.py` and deploy data first."
    )
    st.stop()

# Default to GSE242202 (the muscle-aging-with-decomposition paper) but let
# the user pick any RNA-seq dataset with expression for exploration.
muscle_default = "GSE242202"
candidates = catalog[
    (catalog["has_expression"]) &
    (catalog["platform"].str.contains("RNA", case=False, na=False))
]["accession"].tolist()

if muscle_default in candidates:
    default_idx = candidates.index(muscle_default)
else:
    default_idx = 0 if candidates else None

if not candidates:
    st.warning(
        "No RNA-seq datasets with expression matrices are available yet. "
        "Run `python run_geo_pipeline.py --supplementary --priorities P1 P2 P3` "
        "and `python build_geo_parquet.py`, then deploy."
    )
    st.stop()

acc = st.selectbox(
    "Choose a dataset to decompose",
    options=candidates, index=default_idx,
    format_func=lambda a: f"{a} - {catalog.loc[catalog.accession == a, 'title'].iloc[0][:80]}",
)

# Series-info card
cat_row = catalog[catalog["accession"] == acc].iloc[0]
st.markdown(
    f"""
    <div style='background:{LIGHT_BG};border-left:5px solid {NAVY};
                padding:14px 18px;border-radius:6px;margin:12px 0;'>
    <div style='color:{NAVY};font-size:15px;font-weight:600;'>
        {acc}: {cat_row.title[:120]}
    </div>
    <div style='color:#6B7280;font-size:12px;margin-top:4px;'>
        {cat_row.n_samples} samples &middot; {int(cat_row.n_genes):,} features
        &middot; age {int(cat_row.age_min) if pd.notna(cat_row.age_min) else '?'}-
                    {int(cat_row.age_max) if pd.notna(cat_row.age_max) else '?'}
    </div>
    </div>
    """,
    unsafe_allow_html=True,
)
if cat_row.inexion_relevance:
    st.caption(f"**INEXION relevance.** {cat_row.inexion_relevance}")

# Load + compute
expr_df = _load_geo_expression(acc)
meta_df = _load_geo_metadata(acc)
if expr_df.empty or meta_df.empty:
    st.error(f"Expression or metadata not on disk for {acc}.")
    st.stop()
if "age" not in meta_df.columns or meta_df["age"].notna().sum() < 10:
    st.error(
        f"{acc} has fewer than 10 samples with parsed chronological age. "
        "Decomposition requires age-paired expression."
    )
    st.stop()

# Align expression and metadata on shared sample IDs
common = expr_df.index.intersection(meta_df.index)
expr_df = expr_df.loc[common]
meta_df = meta_df.loc[common]

panels = {
    "Primary aging":         (PRIMARY_AGING_PANEL,  NAVY),
    "Chronic inflammation":  (INFLAMMATION_PANEL,   CORAL),
    "Disuse / atrophy":      (DISUSE_PANEL,         GOLD),
}

results = {}
for name, (panel, color) in panels.items():
    sig, n_resolved, resolved = _compute_signature(expr_df, panel)
    fit = _fit_vs_age(sig, meta_df["age"]) if n_resolved >= 3 else None
    results[name] = {
        "signature":   sig,
        "n_resolved":  n_resolved,
        "resolved":    resolved,
        "fit":         fit,
        "color":       color,
        "panel_size":  len(panel),
    }


# ---- Summary cards strip ----
cs = st.columns(3)
for i, (name, info) in enumerate(results.items()):
    with cs[i]:
        if info["fit"] is None:
            st.markdown(
                f"""
                <div style='background:{LIGHT_BG};border-left:4px solid {info['color']};
                            padding:14px;border-radius:6px;height:130px;'>
                <div style='color:{NAVY};font-weight:700;font-size:14px;
                            text-transform:uppercase;letter-spacing:0.8px;'>
                    {name}
                </div>
                <div style='color:#6B7280;font-size:12px;margin-top:8px;'>
                    Insufficient genes resolved ({info['n_resolved']}/{info['panel_size']}).
                </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            fit = info["fit"]
            st.markdown(
                f"""
                <div style='background:{LIGHT_BG};border-left:4px solid {info['color']};
                            padding:14px;border-radius:6px;height:130px;'>
                <div style='color:{NAVY};font-weight:700;font-size:14px;
                            text-transform:uppercase;letter-spacing:0.8px;'>
                    {name}
                </div>
                <div style='display:flex;gap:18px;margin-top:8px;'>
                    <div>
                        <div style='font-size:11px;color:#6B7280;'>R² vs age</div>
                        <div style='font-size:22px;font-weight:700;color:{info['color']};'>
                            {fit['r_squared']:.3f}
                        </div>
                    </div>
                    <div>
                        <div style='font-size:11px;color:#6B7280;'>Slope (z/yr)</div>
                        <div style='font-size:22px;font-weight:700;color:{NAVY};'>
                            {fit['slope']:+.3f}
                        </div>
                    </div>
                    <div>
                        <div style='font-size:11px;color:#6B7280;'>p</div>
                        <div style='font-size:14px;font-weight:600;color:#1A1A2E;
                                    margin-top:8px;'>
                            {fit['p_value']:.1e}
                        </div>
                    </div>
                </div>
                <div style='color:#6B7280;font-size:11px;margin-top:6px;'>
                    Resolved: {info['n_resolved']}/{info['panel_size']} genes  ·  n={fit['n']}
                </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ---- Decomposition narrative ----
ranked = sorted(
    [(n, r) for n, r in results.items() if r["fit"] is not None],
    key=lambda x: x[1]["fit"]["r_squared"], reverse=True,
)
if ranked:
    top_name, top_info = ranked[0]
    others = [n for n, _ in ranked[1:]]
    st.markdown(
        f"""
        <div style='background:rgba(201,148,26,0.08);border-left:4px solid {GOLD};
                    padding:12px 18px;border-radius:4px;margin:14px 0;'>
        <b>Top age-tracking pathway in this cohort:</b>
        <span style='color:{NAVY};font-weight:600;'>{top_name}</span>
        (R² = {top_info['fit']['r_squared']:.3f}).
        {'Outpaces ' + ' and '.join(others) + ' as the dominant aging signature.' if others else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---- Per-pathway scatter plots ----
st.markdown("#### Pathway signatures vs chronological age")
plot_cols = st.columns(3)
for i, (name, info) in enumerate(results.items()):
    with plot_cols[i]:
        if info["fit"] is None:
            st.info(f"{name}: skipped (insufficient gene coverage).")
            continue
        fit = info["fit"]
        df = fit["df"]
        fig = px.scatter(
            df, x="age", y="sig",
            color_discrete_sequence=[info["color"]], opacity=0.75,
        )
        x_line = np.array([df["age"].min(), df["age"].max()])
        y_line = fit["intercept"] + fit["slope"] * x_line
        fig.add_trace(go.Scatter(
            x=x_line, y=y_line, mode="lines",
            line=dict(color=NAVY, width=2, dash="solid"),
            showlegend=False,
        ))
        fig.update_layout(
            title=name, height=350, plot_bgcolor="white",
            xaxis_title="Chronological age (years)",
            yaxis_title="Pathway signature (z-score sum)",
            margin=dict(t=50, l=50, r=20, b=40),
        )
        fig.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
        fig.update_yaxes(showgrid=True, gridcolor="#E5E7EB")
        st.plotly_chart(fig, use_container_width=True, key=f"sig_{i}")
        st.caption(
            f"R²={fit['r_squared']:.3f}  ·  "
            f"slope={fit['slope']:+.3f} z/yr  ·  "
            f"p={fit['p_value']:.1e}  ·  "
            f"n={fit['n']}"
        )

# ---- Per-pathway gene resolution detail ----
with st.expander("Gene-resolution detail (which panel genes were found)"):
    for name, info in results.items():
        panel = panels[name][0]
        all_genes = list(panel.keys())
        resolved_set = set(info["resolved"])
        resolved_str = ", ".join(
            f"<span style='color:{TEAL};'>{g}</span>" if g in resolved_set
            else f"<span style='color:#B0B0B0;text-decoration:line-through;'>{g}</span>"
            for g in all_genes
        )
        st.markdown(
            f"<b style='color:{NAVY};'>{name}</b> "
            f"({info['n_resolved']}/{len(all_genes)}): {resolved_str}",
            unsafe_allow_html=True,
        )

# ---- Methods caption ----
st.caption(
    "**Methodology.** Each pathway's signature is the signed z-score sum "
    "across resolved panel genes (log1p-transformed counts, per-gene "
    "standardization, sign per gene defined by literature direction with "
    "respect to pathway activity). Pathway score is regressed on "
    "chronological age via OLS; R² and slope reported. Higher R² indicates "
    "the pathway tracks age more strongly in this cohort. The GSE242202 "
    "paper's central claim - that chronic inflammation and inactivity "
    "explain more age-related muscle change than primary aging - implies "
    "inflammation and disuse pathways should out-rank primary aging on "
    "this dataset, which is reproducible here once expression parquet "
    "is loaded."
)
