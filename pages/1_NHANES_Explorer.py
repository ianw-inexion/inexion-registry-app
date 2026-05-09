"""
Cohort Builder — point-and-click filters over NHANES, live count,
descriptive summary, visualizations, CSV export.
"""
import streamlit as st
import plotly.express as px

from src import data
from src.config import BRAND_COLORWAY, NAVY, GOLD
from src.schema import (
    numeric_filter_vars, categorical_filter_vars,
    SEX_LABELS, RACE_LABELS, EDUCATION_LABELS, get_variable,
)


st.set_page_config(page_title="Cohort Builder — INEXION Registry", layout="wide")
st.title("Cohort Builder")
st.caption("Filter the NHANES harmonized dataset. All counts are live.")

# ── Build the filter UI ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filters")

    st.markdown("**Cycles**")
    all_cycles = [
        "1999-2000","2001-2002","2003-2004","2005-2006","2007-2008",
        "2009-2010","2011-2012","2013-2014","2015-2016","2017-2018",
    ]
    cycles = st.multiselect("Cycles", all_cycles, default=all_cycles,
                            label_visibility="collapsed")

    st.markdown("---")
    st.markdown("**Demographics**")
    age_min, age_max = st.slider("Age (years)", 0, 85, (18, 85))
    sex_pick = st.multiselect("Sex", list(SEX_LABELS.values()),
                              default=list(SEX_LABELS.values()))
    race_pick = st.multiselect("Race / Ethnicity", list(RACE_LABELS.values()),
                               default=list(RACE_LABELS.values()))

    st.markdown("---")
    st.markdown("**Biomarker filters** (optional)")

    # A curated set of high-value biomarker filters — keep UI clean, hide the long tail
    featured = [
        ("bmi", "BMI (kg/m²)", 12.0, 70.0, (12.0, 70.0)),
        ("systolic_mean", "Systolic BP (mmHg)", 70, 220, (70, 220)),
        ("hba1c", "HbA1c (%)", 3.5, 18.0, (3.5, 18.0)),
        ("crp", "CRP (mg/L)", 0.0, 200.0, (0.0, 200.0)),
        ("glucose_biopro", "Glucose (mg/dL)", 40, 500, (40, 500)),
        ("phenoage_delta", "PhenoAge delta (years)", -30.0, 40.0, (-30.0, 40.0)),
    ]

    bio_filters = {}
    for key, label, lo, hi, default in featured:
        v = st.slider(label, lo, hi, default, key=f"f_{key}")
        if v != default:
            bio_filters[key] = v

# ── Compose the filter dict ──────────────────────────────────────────────────
filters = {"cycle": cycles, "age": (age_min, age_max)}

sex_map_inv = {v: k for k, v in SEX_LABELS.items()}
race_map_inv = {v: k for k, v in RACE_LABELS.items()}
if sex_pick and len(sex_pick) < len(SEX_LABELS):
    filters["sex"] = [sex_map_inv[s] for s in sex_pick]
if race_pick and len(race_pick) < len(RACE_LABELS):
    filters["race_ethnicity"] = [race_map_inv[r] for r in race_pick]

filters.update(bio_filters)

# ── Render results ───────────────────────────────────────────────────────────
n = data.cohort_count(filters)
total = data.dataset_stats()["n_total"]
pct = (n / total * 100) if total else 0

c1, c2, c3 = st.columns([2, 2, 3])
c1.metric("Cohort size", f"{n:,}", delta=f"{pct:.1f}% of total")
c2.metric("Full dataset", f"{int(total):,}")
c3.markdown(
    f"<div style='background:{NAVY}; color:white; padding:12px 16px; "
    f"border-radius:6px; font-size:13px;'>Active filters: "
    f"{len([k for k,v in filters.items() if v is not None])}</div>",
    unsafe_allow_html=True,
)

if n == 0:
    st.warning("No participants match these filters. Loosen some ranges.")
    st.stop()

# Summary table
st.markdown("### Descriptive summary")
summary = data.cohort_summary(filters)

sc1, sc2, sc3, sc4 = st.columns(4)
sc1.metric("Mean age", f"{summary['mean_age']:.1f}")
sc2.metric("% female", f"{summary['pct_female']*100:.0f}%" if summary['pct_female'] else "—")
sc3.metric("Mean BMI", f"{summary['mean_bmi']:.1f}" if summary['mean_bmi'] else "—")
sc4.metric("Mean PhenoAge Δ",
           f"{summary['mean_phenoage_delta']:+.2f} yr"
           if summary['mean_phenoage_delta'] is not None else "—")

bc1, bc2, bc3, bc4 = st.columns(4)
bc1.metric("Mean systolic", f"{summary['mean_systolic']:.0f}" if summary['mean_systolic'] else "—")
bc2.metric("Mean glucose", f"{summary['mean_glucose']:.0f}" if summary['mean_glucose'] else "—")
bc3.metric("Mean CRP", f"{summary['mean_crp']:.2f}" if summary['mean_crp'] else "—")
bc4.metric("Mean HbA1c", f"{summary['mean_hba1c']:.1f}" if summary['mean_hba1c'] else "—")

# ── Distributions ────────────────────────────────────────────────────────────
st.markdown("### Distribution")
plot_col = st.selectbox(
    "Variable",
    ["phenoage_delta", "kdm_advance", "bmi", "systolic_mean",
     "hba1c", "crp", "age"],
    format_func=lambda k: (get_variable(k) or {}).get("label", k),
)
dist = data.distribution(plot_col, filters)
if len(dist):
    var_meta = get_variable(plot_col) or {}
    fig = px.histogram(
        dist, x="value", nbins=50,
        color_discrete_sequence=[GOLD],
        labels={"value": f"{var_meta.get('label', plot_col)} ({var_meta.get('unit','')})"},
    )
    fig.update_layout(
        bargap=0.02, plot_bgcolor="white", paper_bgcolor="white",
        font_color="#1A1A2E", height=360, margin=dict(t=20, b=40, l=40, r=20),
    )
    st.plotly_chart(fig, width='stretch')

# ── Trend over NHANES cycles ─────────────────────────────────────────────────
st.markdown("### Trend over NHANES cycles")
trend_col = st.selectbox(
    "Variable for cycle trend",
    ["phenoage_delta", "kdm_advance", "bmi", "systolic_mean", "hba1c", "crp"],
    format_func=lambda k: (get_variable(k) or {}).get("label", k),
    key="trend",
)
trend = data.trend_by_cycle(trend_col, filters)
if len(trend):
    var_meta = get_variable(trend_col) or {}
    fig = px.line(
        trend, x="cycle", y="mean_value", markers=True,
        color_discrete_sequence=[NAVY],
        labels={"mean_value": f"Mean {var_meta.get('label', trend_col)}",
                "cycle": "NHANES cycle"},
    )
    fig.update_traces(line=dict(width=3))
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        font_color="#1A1A2E", height=360, margin=dict(t=20, b=40, l=40, r=20),
    )
    st.plotly_chart(fig, width='stretch')

# ── Preview + export ─────────────────────────────────────────────────────────
st.markdown("### Preview")
preview = data.cohort_preview(filters, limit=500)
st.dataframe(preview, width='stretch', height=320)

st.markdown("### Export")
ex_col1, ex_col2 = st.columns([1, 3])
with ex_col1:
    export_limit = st.number_input("Max rows", min_value=100, max_value=200_000,
                                    value=10_000, step=1_000)
with ex_col2:
    st.caption(
        f"Exports up to {export_limit:,} rows of this cohort as CSV. "
        "In the deployed app, every export is audit-logged."
    )

if st.button("Prepare CSV export", type="primary"):
    full = data.cohort_export(filters, max_rows=int(export_limit))
    csv_bytes = full.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=f"inexion_nhanes_cohort_n{len(full)}.csv",
        mime="text/csv",
    )
