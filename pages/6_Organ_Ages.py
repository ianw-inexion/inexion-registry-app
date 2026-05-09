"""
Organ Ages - per-system biological age clocks (SYMPHONYAge-aligned).

Four clocks:
  1. Inflammation (MIDUS, 8 markers)
  2. Liver (NHANES, 6 markers)
  3. Kidney (NHANES, 4 markers)
  4. Metabolic (NHANES, 7 markers)

Each tab shows:
  - Headline Cox HR per 1-yr advance, age-adjusted, with 95% CI and C-index
  - Distribution of advance overall and by age decade
  - Kaplan-Meier survival by advance quintile
  - Correlation with PhenoAge / KDM (where available)

Bottom: inter-clock correlation matrix in NHANES.
"""
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.config import (data_exists, NAVY, GOLD, CORAL, TEAL,
                        NHANES_PARQUET, NHANES_MORTALITY_PARQUET,
                        MIDUS_BIO_PARQUET,
                        ORGAN_CLOCKS_VALIDATION_PATH)

st.set_page_config(page_title="Organ Ages - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Organ Ages</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Per-system biological-age clocks (SYMPHONYAge-aligned) -
            Inflammation, Liver, Kidney, Metabolic
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---- Data loaders ----------------------------------------------------------
@st.cache_data
def load_nhanes():
    if not data_exists(NHANES_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(NHANES_PARQUET)
    if data_exists(NHANES_MORTALITY_PARQUET):
        m = pd.read_parquet(NHANES_MORTALITY_PARQUET,
                            columns=["seqn", "years_int_to_event", "mortality_status"])
        m = m.rename(columns={"years_int_to_event": "years_to_event"})
        df = df.merge(m, on="seqn", how="left")
    return df


@st.cache_data
def load_midus():
    if not data_exists(MIDUS_BIO_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(MIDUS_BIO_PARQUET)


@st.cache_data
def load_validation():
    """Load Cox HR + C-index per clock from organ_clocks_validation.json."""
    try:
        if data_exists(ORGAN_CLOCKS_VALIDATION_PATH):
            from src.config import IS_S3
            if IS_S3:
                import s3fs
                fs = s3fs.S3FileSystem(anon=False)
                with fs.open(str(ORGAN_CLOCKS_VALIDATION_PATH), "r") as f:
                    return json.load(f)
            with open(ORGAN_CLOCKS_VALIDATION_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []


nh   = load_nhanes()
md   = load_midus()
vals = load_validation()
val_by_label = {v["label"]: v for v in vals}


# ---- Helpers ---------------------------------------------------------------
def _km_quintile(df, advance_col, time_col="years_to_event", event_col="mortality_status"):
    """Return KM curves for each quintile of advance."""
    try:
        from lifelines import KaplanMeierFitter
    except ImportError:
        return None
    sub = df[[advance_col, time_col, event_col]].dropna().copy()
    sub = sub[sub[time_col] > 0]
    if len(sub) < 200:
        return None
    sub["q"] = pd.qcut(sub[advance_col], 5, labels=["Q1 (lowest)", "Q2", "Q3", "Q4", "Q5 (highest)"])
    fig = go.Figure()
    palette = [TEAL, "#7FB069", GOLD, "#E8A85B", CORAL]
    for q, color in zip(["Q1 (lowest)", "Q2", "Q3", "Q4", "Q5 (highest)"], palette):
        s = sub[sub["q"] == q]
        if len(s) < 30:
            continue
        kmf = KaplanMeierFitter()
        kmf.fit(s[time_col], s[event_col], label=str(q))
        sf = kmf.survival_function_
        fig.add_trace(go.Scatter(
            x=sf.index, y=sf.iloc[:, 0],
            mode="lines", name=str(q),
            line=dict(color=color, width=2.5),
        ))
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", font_color="#1A1A2E",
        height=380,
        xaxis_title="Years from baseline",
        yaxis=dict(title="Survival probability", range=[0.5, 1.01]),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def _hero(label, n_train=None):
    """Render the header card for a clock tab using validation results."""
    v = val_by_label.get(label)
    if v is None:
        st.warning(f"No validation results yet for {label}. Re-run build_organ_clocks.py.")
        return
    hr = v["hr"]
    lo, hi = v["hr_lo"], v["hr_hi"]
    cidx = v["c_index"]
    pct = (hr - 1.0) * 100
    color = CORAL if hr > 1.0 else TEAL
    st.markdown(
        f"""<div style='background:{NAVY};color:white;padding:24px 28px;
                    border-radius:10px;margin:8px 0 16px 0;'>
            <div style='color:{GOLD};font-size:11px;letter-spacing:2px;
                        text-transform:uppercase;'>{label} - age-adjusted Cox PH</div>
            <div style='display:flex;gap:48px;margin-top:12px;align-items:flex-end;'>
                <div>
                    <div style='font-size:48px;font-weight:800;color:{color};line-height:1;'>
                        {hr:.3f}
                    </div>
                    <div style='font-size:12px;color:#C9CBD4;margin-top:4px;'>
                        HR per 1-yr advance &nbsp; [{lo:.3f}, {hi:.3f}]
                    </div>
                </div>
                <div>
                    <div style='font-size:36px;font-weight:700;color:{GOLD};line-height:1;'>
                        {cidx:.3f}
                    </div>
                    <div style='font-size:12px;color:#C9CBD4;margin-top:4px;'>C-index</div>
                </div>
                <div>
                    <div style='font-size:24px;font-weight:600;color:white;line-height:1;'>
                        {v['n']:,}  /  {v['events']:,}
                    </div>
                    <div style='font-size:12px;color:#C9CBD4;margin-top:4px;'>n analytic / events</div>
                </div>
                <div>
                    <div style='font-size:24px;font-weight:600;color:white;line-height:1;'>
                        {pct:+.1f}%
                    </div>
                    <div style='font-size:12px;color:#C9CBD4;margin-top:4px;'>mortality risk per +1 yr</div>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def _distribution(df, advance_col, age_col, label, color):
    sub = df[[advance_col, age_col]].dropna().copy()
    if sub.empty:
        st.info(f"No advance values to plot for {label}.")
        return
    sub["age_decade"] = (sub[age_col] // 10 * 10).astype(int).clip(20, 80)
    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(sub, x=advance_col, nbins=60,
                           title=f"{label} advance distribution",
                           color_discrete_sequence=[color],
                           labels={advance_col: "Advance (years)"})
        fig.add_vline(x=0, line_dash="dash", line_color="gray",
                      annotation_text="No advance")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          font_color="#1A1A2E", height=320,
                          margin=dict(t=40, b=40, l=40, r=20))
        st.plotly_chart(fig, width="stretch", key=f"oa_{label}_dist")
    with col2:
        ag = sub.groupby("age_decade")[advance_col].agg(["mean", "std", "count"]).reset_index()
        fig2 = px.bar(ag, x="age_decade", y="mean",
                      error_y="std",
                      title=f"Mean {label.lower()} advance by age decade",
                      color_discrete_sequence=[color],
                      labels={"age_decade": "Chronological age (decade)",
                              "mean": "Mean advance (years)"})
        fig2.add_hline(y=0, line_dash="dash", line_color="gray")
        fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           font_color="#1A1A2E", height=320,
                           margin=dict(t=40, b=40, l=40, r=20))
        st.plotly_chart(fig2, width="stretch", key=f"oa_{label}_decade")


def _km_block(df, advance_col, label):
    fig = _km_quintile(df, advance_col)
    if fig is None:
        st.caption("Kaplan-Meier survival curve unavailable (lifelines missing or too few events).")
        return
    fig.update_layout(title=f"Kaplan-Meier survival by quintile of {label.lower()} advance")
    st.plotly_chart(fig, width="stretch", key=f"oa_{label}_km")


def _scatter_vs(df, advance_col, vs_col, label, vs_label):
    sub = df[[advance_col, vs_col]].dropna()
    if len(sub) < 50:
        return
    sub = sub.sample(min(3000, len(sub)), random_state=42)
    r = sub[[advance_col, vs_col]].corr().iloc[0, 1]
    fig = px.scatter(sub, x=advance_col, y=vs_col,
                     opacity=0.35,
                     color_discrete_sequence=[NAVY],
                     title=f"{label} advance vs {vs_label}  (r={r:+.3f})",
                     labels={advance_col: f"{label} advance (yrs)",
                             vs_col: vs_label})
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                      font_color="#1A1A2E", height=320)
    st.plotly_chart(fig, width="stretch", key=f"oa_{label}_vs_{vs_col}")


# ---- Tabs ------------------------------------------------------------------
tabs = st.tabs(["Inflammation (MIDUS)", "Liver (NHANES)",
                "Kidney (NHANES)", "Metabolic (NHANES)",
                "Cross-clock correlations"])


# Tab 1 - Inflammation
with tabs[0]:
    if md.empty or "inflammation_advance" not in md.columns:
        st.warning("Inflammation Age not yet trained in MIDUS. Run build_organ_clocks.py.")
    else:
        st.caption(
            "8 inflammation markers - log(CRP), log(IL-6), log(IL-8), log(IL-10), "
            "log(TNF-alpha), fibrinogen, sICAM-1, sE-selectin. "
            "Trained within MIDUS adults aged 30-75."
        )
        _hero("MIDUS Inflammation")
        _distribution(md, "inflammation_advance", "age", "Inflammation", CORAL)
        _km_block(md, "inflammation_advance", "MIDUS Inflammation")
        if "kdm_advance" in md.columns:
            _scatter_vs(md, "inflammation_advance", "kdm_advance",
                        "Inflammation", "KDM advance (MIDUS)")


# Tab 2 - Liver
with tabs[1]:
    if nh.empty or "liver_advance" not in nh.columns:
        st.warning("Liver Age not yet trained in NHANES. Run build_organ_clocks.py.")
    else:
        st.caption(
            "6 hepatic markers - albumin, alkaline phosphatase, total bilirubin, "
            "total protein, platelet count, LDH. ALT / AST / GGT not yet ingested "
            "into the NHANES parquet, so this is a hepatic-synthetic-function "
            "panel rather than a hepatocellular-injury panel."
        )
        _hero("NHANES Liver")
        _distribution(nh, "liver_advance", "age", "Liver", "#A66B36")
        _km_block(nh, "liver_advance", "NHANES Liver")
        if "phenoage_delta" in nh.columns:
            _scatter_vs(nh, "liver_advance", "phenoage_delta",
                        "Liver", "PhenoAge delta")


# Tab 3 - Kidney
with tabs[2]:
    if nh.empty or "kidney_advance" not in nh.columns:
        st.warning("Kidney Age not yet trained in NHANES.")
    else:
        st.caption(
            "Creatinine, BUN, uric acid, plus computed CKD-EPI 2021 eGFR "
            "(race-free). Trained within NHANES adults aged 30-75."
        )
        _hero("NHANES Kidney")
        _distribution(nh, "kidney_advance", "age", "Kidney", TEAL)
        _km_block(nh, "kidney_advance", "NHANES Kidney")
        if "phenoage_delta" in nh.columns:
            _scatter_vs(nh, "kidney_advance", "phenoage_delta",
                        "Kidney", "PhenoAge delta")


# Tab 4 - Metabolic
with tabs[3]:
    if nh.empty or "metabolic_advance" not in nh.columns:
        st.warning("Metabolic Age not yet trained in NHANES.")
    else:
        st.caption(
            "HbA1c, total cholesterol, HDL, BMI, waist circumference, systolic + "
            "diastolic BP. (Fasting glucose / insulin / HOMA-IR excluded - "
            "subsample-only in NHANES.)"
        )
        _hero("NHANES Metabolic")
        _distribution(nh, "metabolic_advance", "age", "Metabolic", GOLD)
        _km_block(nh, "metabolic_advance", "NHANES Metabolic")
        if "phenoage_delta" in nh.columns:
            _scatter_vs(nh, "metabolic_advance", "phenoage_delta",
                        "Metabolic", "PhenoAge delta")


# Tab 5 - Cross-clock correlations
with tabs[4]:
    st.markdown("#### Inter-clock correlation matrix")
    st.caption(
        "How much does each organ-age clock agree with the others, plus the "
        "biomarker-PhenoAge and KDM advance? High correlation -> clocks are "
        "picking up the same underlying biological signal. Low correlation -> "
        "they are giving complementary information."
    )

    if not nh.empty:
        cols = [c for c in ["liver_advance", "kidney_advance", "metabolic_advance",
                            "phenoage_delta", "kdm_advance"] if c in nh.columns]
        labels = {"liver_advance":     "Liver",
                  "kidney_advance":    "Kidney",
                  "metabolic_advance": "Metabolic",
                  "phenoage_delta":    "PhenoAge delta",
                  "kdm_advance":       "KDM advance"}
        sub = nh[cols].dropna(how="any")
        if len(sub) > 100:
            corr = sub.corr().rename(index=labels, columns=labels)
            st.markdown(f"**NHANES**  -  pairwise n = {len(sub):,}")
            fig = px.imshow(corr.round(2), text_auto=True, aspect="equal",
                            color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                              font_color="#1A1A2E", height=420,
                              margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig, width="stretch", key="oa_corr_nhanes")

    if not md.empty:
        md_cols = [c for c in ["inflammation_advance", "kidney_advance",
                               "metabolic_advance", "kdm_advance"] if c in md.columns]
        md_labels = {"inflammation_advance": "Inflammation",
                     "kidney_advance":       "Kidney",
                     "metabolic_advance":    "Metabolic",
                     "kdm_advance":          "KDM advance"}
        sub_md = md[md_cols].dropna(how="any")
        if len(sub_md) > 100:
            corr_md = sub_md.corr().rename(index=md_labels, columns=md_labels)
            st.markdown(f"**MIDUS**  -  pairwise n = {len(sub_md):,}")
            fig = px.imshow(corr_md.round(2), text_auto=True, aspect="equal",
                            color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                              font_color="#1A1A2E", height=380,
                              margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig, width="stretch", key="oa_corr_midus")

    st.caption(
        "Methodology: each clock = OLS regression of chronological age on the "
        "organ's biomarker panel, trained on adults 30-75 within the cohort. "
        "Advance = predicted organ age - chronological age. All Cox HRs above "
        "are age-adjusted to remove regression-to-the-mean confounding. "
        "Compatible with SYMPHONYAge methodology - Raghav can plug in his "
        "trained models in place of the within-cohort fits."
    )
