"""
MIDUS Explorer
==============
Three biomarker waves (M2 / Refresher 1 / M3, 2004-2022) plus the
M3 BTACT cognitive battery, with MIDUS-anchored KDM biological age.

MIDUS is the registry's allostatic-load and inflammation-aging cohort:
- 9-marker inflammation panel (CRP, IL-6/8/10, TNF-alpha, fibrinogen,
  sICAM-1, sE-selectin, sUPAR) - rare across longevity cohorts
- Cardiometabolic suite (HbA1c, lipids, glucose/insulin/HOMA-IR)
- Neuroendocrine (DHEA-S, IGF-1, urinary cortisol, catecholamines)
- KDM biological age computed with within-MIDUS reference parameters
  (NHANES III parameters yielded a -19.8 yr cohort-mismatch artifact)

Note: MIDUS lacks the full PhenoAge panel (no WBC, MCV, RDW,
lymphocyte%, total ALP; B4BALBUMIN is urinary albumin, not serum).
PhenoAge analyses use NHANES + HRS VBS instead.
"""
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.config import (
    data_exists, NAVY, GOLD, CORAL, TEAL, BRAND_COLORWAY,
    MIDUS_BIO_PARQUET, MIDUS_COG_PARQUET, MIDUS_CODEBOOK_PARQUET,
    DATA_DIR, IS_S3,
)

st.set_page_config(page_title="MIDUS Explorer - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            MIDUS Explorer</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Midlife in the United States - 3 biomarker waves (2004-2022, n=2,865)
            + M3 cognitive battery (n=3,291)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Data loaders ------------------------------------------------------

@st.cache_data
def load_bio():
    if not data_exists(MIDUS_BIO_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(MIDUS_BIO_PARQUET)
    # Wave display labels
    wave_labels = {
        "MIDUS2":          "MIDUS 2 (2004-2009)",
        "MIDUS_Refresher1":"MIDUS Refresher 1 (2012-2016)",
        "MIDUS3":          "MIDUS 3 (2017-2022)",
    }
    df["wave_label"] = df["wave"].map(wave_labels).fillna(df["wave"])
    # Sex display
    df["sex_label"] = df["sex"].map({"M":"Male", "F":"Female"}).fillna("Unknown")
    df["age_decile"] = pd.cut(
        df["age"],
        bins=[0, 30, 40, 50, 60, 70, 80, 120],
        labels=["<30","30s","40s","50s","60s","70s","80+"],
        include_lowest=True,
    )
    return df

@st.cache_data
def load_cog():
    if not data_exists(MIDUS_COG_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(MIDUS_COG_PARQUET)

@st.cache_data
def load_kdm_params():
    """Load the trained KDM parameters JSON if available locally."""
    candidates = []
    if not IS_S3:
        candidates.append(Path(DATA_DIR) / "midus_kdm_params.json")
    for p in candidates:
        if p and p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    return None


bio = load_bio()
cog = load_cog()
kdm_params = load_kdm_params()

if bio.empty:
    st.error("MIDUS biomarker parquet not found. Check S3 / local data path.")
    st.stop()

# ---------- Sidebar filters ---------------------------------------------------

with st.sidebar:
    st.markdown("### MIDUS Filters")
    age_min, age_max = int(bio["age"].min()), int(bio["age"].max())
    age_range = st.slider("Age range", age_min, age_max, (age_min, age_max), key="midus_age")
    sexes  = sorted([s for s in bio["sex_label"].dropna().unique() if s != "Unknown"])
    sex_sel = st.multiselect("Sex", sexes, default=sexes, key="midus_sex")
    wave_sel = st.multiselect(
        "Wave",
        bio["wave_label"].unique().tolist(),
        default=bio["wave_label"].unique().tolist(),
        key="midus_wave",
    )

filt = bio[
    bio["age"].between(*age_range) &
    bio["sex_label"].isin(sex_sel) &
    bio["wave_label"].isin(wave_sel)
].copy()

if filt.empty:
    st.warning("No MIDUS respondents match the current filters.")
    st.stop()

# ---------- Tabs --------------------------------------------------------------

tabs = st.tabs([
    "Overview",
    "Inflammation Panel",
    "Cardiometabolic",
    "Neuroendocrine",
    "Wave Comparison",
    "Cognition (M3)",
])

# =============================================================================
# TAB 1 - OVERVIEW
# =============================================================================
with tabs[0]:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Respondents", f"{len(filt):,}")
    c2.metric("Mean age", f"{filt['age'].mean():.1f}")
    valid_kdm = filt["kdm_bioage"].notna()
    if valid_kdm.any():
        c3.metric("Mean KDM bioage", f"{filt.loc[valid_kdm,'kdm_bioage'].mean():.1f}")
        c4.metric(
            "Mean KDM advance",
            f"{filt.loc[valid_kdm,'kdm_advance'].mean():+.2f} yrs",
            help="Biological age minus chronological age. Centered at 0 by construction in the reference window (ages 30-75)."
        )
        c5.metric(
            "% Accelerated",
            f"{(filt.loc[valid_kdm,'kdm_advance']>0).mean()*100:.0f}%",
        )

    st.markdown("##### KDM advance distribution")
    if valid_kdm.any():
        fig = px.histogram(
            filt[valid_kdm], x="kdm_advance", color="wave_label",
            nbins=40, opacity=0.7,
            color_discrete_sequence=BRAND_COLORWAY,
            labels={"kdm_advance":"KDM advance (yrs)", "wave_label":"Wave"},
        )
        fig.update_layout(barmode="overlay", height=320, legend_title_text="")
        fig.add_vline(x=0, line_dash="dash", line_color=NAVY)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Wave summary")
    summary_rows = []
    for w in sorted(filt["wave_label"].unique()):
        sub = filt[filt["wave_label"]==w]
        v = sub["kdm_bioage"].notna()
        summary_rows.append({
            "Wave": w,
            "n": len(sub),
            "Mean age": round(sub["age"].mean(), 1),
            "Mean KDM advance": (round(sub.loc[v,"kdm_advance"].mean(),2)
                                  if v.any() else None),
            "SD KDM advance":   (round(sub.loc[v,"kdm_advance"].std(),2)
                                  if v.any() else None),
            "Mean CRP (mg/L)":  round(sub["crp_mg_l"].mean(), 2),
            "Mean HbA1c (%)":   round(sub["hba1c_pct"].mean(), 2),
            "Mean SBP":         round(sub["systolic_bp_mean"].mean(), 1),
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    if kdm_params:
        with st.expander("KDM training parameters (within-MIDUS)"):
            tw = kdm_params.get("training_window", [])
            st.caption(
                f"Trained on ages {tw[0]}-{tw[1]}, OLS biomarker on age. "
                f"Min markers required for KDM: {kdm_params.get('min_markers_required_for_kdm','-')}."
            )
            rows = []
            for bm, p in kdm_params.get("biomarkers", {}).items():
                rows.append({
                    "Biomarker": bm,
                    "Scale": "ln" if p.get("log_transformed") else "raw",
                    "k (intercept)": round(p["k"], 4),
                    "q (slope/yr)":  round(p["q"], 5),
                    "s (resid SD)":  round(p["s"], 4),
                    "R^2":           round(p["r2"], 4),
                    "n":             p["n"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# =============================================================================
# TAB 2 - INFLAMMATION PANEL
# =============================================================================
with tabs[1]:
    st.caption(
        "MIDUS's distinctive contribution to the registry: a 9-marker "
        "circulating inflammation panel rarely available in other longevity cohorts."
    )
    inflam_vars = [
        ("crp_mg_l",   "CRP (mg/L)",       True),
        ("il6_msd",    "IL-6 (pg/mL)",      True),
        ("il8",        "IL-8 (pg/mL)",      True),
        ("il10",       "IL-10 (pg/mL)",     True),
        ("tnf_alpha",  "TNF-alpha (pg/mL)", True),
        ("fibrinogen", "Fibrinogen (mg/dL)",False),
        ("sicam",      "sICAM-1 (ng/mL)",   False),
        ("seselectin", "sE-selectin (ng/mL)",False),
        ("supar",      "sUPAR (ng/mL)",     False),
    ]

    cov_rows = []
    for col, label, _ in inflam_vars:
        if col in filt.columns:
            n = filt[col].notna().sum()
            cov_rows.append({"Marker": label, "n": int(n),
                              "Mean": round(filt[col].mean(),3),
                              "Median": round(filt[col].median(),3)})
    st.dataframe(pd.DataFrame(cov_rows), use_container_width=True, hide_index=True)

    st.markdown("##### Distributions (log-scale where right-skewed)")
    cols_per_row = 3
    rows_needed = (len(inflam_vars) + cols_per_row - 1) // cols_per_row
    for r in range(rows_needed):
        cs = st.columns(cols_per_row)
        for c, (col, label, log_scale) in enumerate(inflam_vars[r*cols_per_row:(r+1)*cols_per_row]):
            with cs[c]:
                if col in filt.columns and filt[col].notna().sum() > 0:
                    sub = filt[filt[col].notna()].copy()
                    fig = px.histogram(
                        sub, x=col, nbins=30,
                        color_discrete_sequence=[NAVY],
                        labels={col: label},
                        log_x=log_scale,
                    )
                    fig.update_layout(height=220, margin=dict(l=10,r=10,t=10,b=10),
                                       showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Correlations with KDM advance and age")
    corr_targets = [c for c,_,_ in inflam_vars if c in filt.columns]
    rows = []
    for c in corr_targets:
        sub = filt[[c, "kdm_advance", "age"]].dropna()
        if len(sub) < 30:
            continue
        # Use log for skewed markers when computing corr
        v = np.log(np.maximum(sub[c].values.astype(float), 1e-3)) \
            if dict((cc, ls) for cc, _, ls in inflam_vars).get(c) else sub[c].values
        rows.append({
            "Marker": dict((cc, lab) for cc, lab, _ in inflam_vars).get(c, c),
            "n": len(sub),
            "r vs KDM advance": round(np.corrcoef(v, sub["kdm_advance"])[0,1], 3),
            "r vs age":         round(np.corrcoef(v, sub["age"])[0,1], 3),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# =============================================================================
# TAB 3 - CARDIOMETABOLIC
# =============================================================================
with tabs[2]:
    st.caption(
        "Glycemic control, lipid panel, and insulin resistance - 3-wave "
        "harmonized panel."
    )

    cm_pairs = [
        ("hba1c_pct",        "HbA1c (%)"),
        ("glucose_mg_dl",    "Fasting glucose (mg/dL)"),
        ("homair",           "HOMA-IR"),
        ("total_cholesterol","Total cholesterol (mg/dL)"),
        ("hdl",              "HDL (mg/dL)"),
        ("ldl",              "LDL (mg/dL)"),
        ("triglycerides",    "Triglycerides (mg/dL)"),
        ("creatinine_mg_dl", "Creatinine (mg/dL)"),
    ]

    st.markdown("##### Distributions by wave")
    cols_per_row = 4
    for r in range((len(cm_pairs)+cols_per_row-1)//cols_per_row):
        cs = st.columns(cols_per_row)
        for c, (col, label) in enumerate(cm_pairs[r*cols_per_row:(r+1)*cols_per_row]):
            with cs[c]:
                if col in filt.columns and filt[col].notna().sum() > 0:
                    fig = px.box(
                        filt[filt[col].notna()],
                        x="wave_label", y=col, color="wave_label",
                        color_discrete_sequence=BRAND_COLORWAY,
                        labels={col: label, "wave_label": ""},
                        points=False,
                    )
                    fig.update_layout(height=240, margin=dict(l=10,r=10,t=30,b=10),
                                       showlegend=False, title=label, title_font_size=12)
                    st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### HbA1c and HOMA-IR by age decile")
    has_hba1c = filt["hba1c_pct"].notna().sum() > 0
    has_homa  = filt["homair"].notna().sum() > 0
    cols = st.columns(2)
    if has_hba1c:
        with cols[0]:
            ag = (filt[filt["hba1c_pct"].notna()]
                  .groupby("age_decile", observed=True)["hba1c_pct"]
                  .agg(["mean","count"]).reset_index())
            fig = px.bar(ag, x="age_decile", y="mean",
                         color_discrete_sequence=[GOLD],
                         labels={"age_decile":"Age decile","mean":"Mean HbA1c (%)"})
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    if has_homa:
        with cols[1]:
            ag = (filt[filt["homair"].notna()]
                  .groupby("age_decile", observed=True)["homair"]
                  .agg(["mean","count"]).reset_index())
            fig = px.bar(ag, x="age_decile", y="mean",
                         color_discrete_sequence=[CORAL],
                         labels={"age_decile":"Age decile","mean":"Mean HOMA-IR"})
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# TAB 4 - NEUROENDOCRINE
# =============================================================================
with tabs[3]:
    st.caption(
        "Steroid axis decline (DHEA-S, IGF-1) and 12-hr urinary "
        "cortisol / catecholamine output. Note urinary measurements - "
        "use within-cohort comparisons rather than absolute clinical cutoffs."
    )

    ne_pairs = [
        ("dheas",                       "DHEA-S (ug/dL)"),
        ("dhea",                        "DHEA (ng/mL)"),
        ("igf1",                        "IGF-1 (ng/mL)"),
        ("urinary_cortisol_12h",        "Urinary cortisol 12hr (ug/dL)"),
        ("urinary_cortisone_overnight", "Urinary cortisone overnight (ug/dL)"),
        ("urinary_norepi",              "Urinary norepinephrine (ug/dL)"),
        ("urinary_epi",                 "Urinary epinephrine (ug/dL)"),
        ("urinary_dopa",                "Urinary dopamine (ug/dL)"),
    ]

    st.markdown("##### DHEA-S vs age (classic steroid decline)")
    if "dheas" in filt.columns and filt["dheas"].notna().sum() > 30:
        sub = filt[filt["dheas"].notna()].copy()
        fig = px.scatter(
            sub, x="age", y="dheas", color="sex_label",
            color_discrete_sequence=[NAVY, CORAL],
            opacity=0.5,
            labels={"age":"Age", "dheas":"DHEA-S (ug/dL)", "sex_label":"Sex"},
            trendline="lowess",
        )
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Distributions by sex")
    cols_per_row = 4
    for r in range((len(ne_pairs)+cols_per_row-1)//cols_per_row):
        cs = st.columns(cols_per_row)
        for c, (col, label) in enumerate(ne_pairs[r*cols_per_row:(r+1)*cols_per_row]):
            with cs[c]:
                if col in filt.columns and filt[col].notna().sum() > 0:
                    sub = filt[filt[col].notna()]
                    fig = px.box(
                        sub, x="sex_label", y=col, color="sex_label",
                        color_discrete_sequence=[NAVY, CORAL],
                        labels={col: "", "sex_label": ""},
                        points=False,
                    )
                    fig.update_layout(height=220, margin=dict(l=10,r=10,t=30,b=10),
                                       showlegend=False, title=label, title_font_size=12)
                    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# TAB 5 - WAVE COMPARISON
# =============================================================================
with tabs[4]:
    st.caption(
        "Secular trends across 18 years. NB: M2 (2004-09) and MR1 (2012-16) "
        "draw from different MIDUS sample frames; M3 (2017-22) is the M2 "
        "cohort followed up. Treat cross-wave differences as a mix of "
        "secular and cohort effects."
    )

    metric_pairs = [
        ("kdm_advance",      "KDM advance (yrs)"),
        ("crp_mg_l",         "CRP (mg/L)"),
        ("il6_msd",          "IL-6 (pg/mL)"),
        ("hba1c_pct",        "HbA1c (%)"),
        ("homair",           "HOMA-IR"),
        ("systolic_bp_mean", "Mean SBP (mmHg)"),
        ("total_cholesterol","Total cholesterol (mg/dL)"),
        ("dheas",            "DHEA-S (ug/dL)"),
    ]

    rows = []
    waves_in_data = sorted(bio["wave_label"].unique())
    for col, label in metric_pairs:
        if col not in bio.columns:
            continue
        row = {"Metric": label}
        for w in waves_in_data:
            sub = bio[bio["wave_label"]==w]
            v = sub[col].dropna()
            row[f"{w} mean"] = round(float(v.mean()),3) if len(v) else None
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("##### KDM advance distribution by wave (filtered cohort)")
    if filt["kdm_advance"].notna().sum() > 30:
        fig = px.violin(
            filt[filt["kdm_advance"].notna()],
            x="wave_label", y="kdm_advance", color="wave_label",
            color_discrete_sequence=BRAND_COLORWAY,
            box=True, points=False,
            labels={"wave_label":"Wave", "kdm_advance":"KDM advance (yrs)"},
        )
        fig.update_layout(height=380, showlegend=False)
        fig.add_hline(y=0, line_dash="dash", line_color=NAVY)
        st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# TAB 6 - COGNITION (M3)
# =============================================================================
with tabs[5]:
    if cog.empty:
        st.info("MIDUS 3 cognitive parquet not found.")
    else:
        st.caption(
            "Brief Test of Adult Cognition by Telephone (BTACT) for the M3 "
            "subsample (n=3,291). Joined to the M3 biomarker visit by M2ID."
        )
        # Filter cognitive to filtered cohort (by age + sex), then merge bio
        cog_sub = cog.copy()
        if "age" in cog_sub.columns:
            cog_sub = cog_sub[cog_sub["age"].between(*age_range)]
        if "sex" in cog_sub.columns:
            cog_sub = cog_sub[cog_sub["sex"].isin(["M","F"])]
            sex_map = {"M":"Male","F":"Female"}
            cog_sub["sex_label"] = cog_sub["sex"].map(sex_map)
            cog_sub = cog_sub[cog_sub["sex_label"].isin(sex_sel)]

        c1, c2, c3 = st.columns(3)
        c1.metric("Respondents (filtered)", f"{len(cog_sub):,}")
        if "wordlist_total_unique" in cog_sub.columns:
            c2.metric("Mean word recall (unique)",
                       f"{cog_sub['wordlist_total_unique'].mean():.2f}")
        if "category_fluency_unique" in cog_sub.columns:
            c3.metric("Mean category fluency",
                       f"{cog_sub['category_fluency_unique'].mean():.2f}")

        # Biomarker -> cognition link: merge with M3 biomarker subset only
        m3 = bio[bio["wave"]=="MIDUS3"][["midus_id","kdm_advance","crp_mg_l","il6_msd","hba1c_pct"]].copy()
        merged = cog_sub.merge(m3, on="midus_id", how="inner")
        if not merged.empty:
            st.markdown(
                f"##### Biomarker -> Cognition link (M3 overlap, n={len(merged):,})"
            )
            cog_outcomes = [
                ("wordlist_total_unique", "Word recall (unique)"),
                ("digit_span_back_score", "Digit span backward"),
                ("category_fluency_unique","Category fluency"),
                ("number_series_total",     "Number series total (BTACT)"),
            ]
            corr_rows = []
            for col, label in cog_outcomes:
                if col not in merged.columns:
                    continue
                # Coerce to numeric defensively - some BTACT vars come through as
                # ICPSR factor categoricals ("(1) YES" / "(2) NO" etc.).
                y_num = pd.to_numeric(merged[col], errors="coerce")
                for biom in ["kdm_advance","crp_mg_l","il6_msd","hba1c_pct"]:
                    if biom not in merged.columns:
                        continue
                    x_num = pd.to_numeric(merged[biom], errors="coerce")
                    pair = pd.DataFrame({"y": y_num, "x": x_num}).dropna()
                    if len(pair) < 30:
                        continue
                    xv = pair["x"].values.astype(float)
                    yv = pair["y"].values.astype(float)
                    if biom in ("crp_mg_l","il6_msd"):
                        xv = np.log(np.maximum(xv, 1e-3))
                    if np.std(xv) == 0 or np.std(yv) == 0:
                        continue
                    r = float(np.corrcoef(xv, yv)[0,1])
                    corr_rows.append({"Cognitive outcome": label, "Biomarker": biom,
                                       "n": len(pair), "r": round(r, 3)})
            if corr_rows:
                st.dataframe(pd.DataFrame(corr_rows), use_container_width=True, hide_index=True)

            st.markdown("##### KDM advance vs word recall (M3 overlap)")
            if "wordlist_total_unique" in merged.columns:
                sub = merged[["kdm_advance","wordlist_total_unique","sex_label"]].dropna()
                if len(sub) > 30:
                    fig = px.scatter(
                        sub, x="kdm_advance", y="wordlist_total_unique",
                        color="sex_label",
                        color_discrete_sequence=[NAVY, CORAL],
                        opacity=0.5,
                        labels={"kdm_advance":"KDM advance (yrs)",
                                "wordlist_total_unique":"Words recalled (unique)",
                                "sex_label":"Sex"},
                        trendline="ols",
                    )
                    fig.update_layout(height=360)
                    st.plotly_chart(fig, use_container_width=True)
