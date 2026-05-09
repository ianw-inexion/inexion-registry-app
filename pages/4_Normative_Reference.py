"""
Normative Reference Lookup — where does a patient stand in the U.S. population?

Given age, sex, and PhenoAge delta, computes the patient's percentile rank
in the NHANES reference population for their age-sex group.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats
from src.config import NAVY, GOLD, CORAL, TEAL, NHANES_PARQUET

st.set_page_config(page_title="Normative Reference — INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Normative Reference Lookup</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Where does a patient stand relative to the U.S. population? ·
            Reference: NHANES 2001–2018 (n=29,779 with PhenoAge)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

@st.cache_data
def load_reference():
    df = pd.read_parquet(NHANES_PARQUET,
        columns=['age','sex','phenoage_delta','phenoage','exam_weight_adj'])
    df = df[df['phenoage_delta'].notna() & df['age'].between(20, 85)].copy()
    df['sex_label'] = df['sex'].map({1:'Male', 2:'Female'})
    df['age_group'] = pd.cut(df['age'],
        bins=[19,29,39,49,59,69,79,85],
        labels=['20–29','30–39','40–49','50–59','60–69','70–79','80+'])
    return df

ref = load_reference()

# ── Patient input ─────────────────────────────────────────────────────────────
st.markdown("### Patient Profile")
col1, col2, col3 = st.columns(3)
with col1:
    patient_age  = st.number_input("Age (years)", 20, 85, 55)
with col2:
    patient_sex  = st.selectbox("Sex", ["Male", "Female"])
with col3:
    patient_delta = st.number_input(
        "PhenoAge Delta (years)",
        -30.0, 50.0, 0.0, step=0.1,
        help="Biological age minus chronological age. Positive = aging faster than average."
    )

st.caption(
    "Enter PhenoAge delta directly, or compute it first on the Biological Age Calculator page. "
    "Negative delta = biologically younger than average. Positive = older."
)

# ── Matching reference cohort ─────────────────────────────────────────────────
age_bin = max(20, min(79, (patient_age // 10) * 10))
age_lo, age_hi = age_bin, age_bin + 9
sex_code = 1 if patient_sex == "Male" else 2

ref_cohort = ref[
    ref['age'].between(age_lo, age_hi) &
    (ref['sex'] == sex_code) &
    ref['phenoage_delta'].notna()
]

if len(ref_cohort) < 50:
    # Expand age window if too few
    ref_cohort = ref[
        ref['age'].between(max(20, age_lo - 10), min(85, age_hi + 10)) &
        (ref['sex'] == sex_code) &
        ref['phenoage_delta'].notna()
    ]

n_ref = len(ref_cohort)
deltas = ref_cohort['phenoage_delta'].values
percentile = float(stats.percentileofscore(deltas, patient_delta, kind='rank'))

# ── Results ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Results")

pct_color = CORAL if percentile > 75 else (TEAL if percentile < 25 else GOLD)
direction = "faster" if patient_delta > 0 else "slower"
interpretation = (
    f"This patient's biomarkers resemble those of someone biologically "
    f"{abs(patient_delta):.1f} years {'older' if patient_delta > 0 else 'younger'} "
    f"than their chronological age. Among {patient_sex.lower()}s aged {age_lo}–{age_hi} "
    f"in the U.S. population (NHANES 2001–2018, n={n_ref:,}), this patient is at the "
    f"**{percentile:.0f}th percentile** of biological age acceleration — aging "
    f"{direction} than {100 - percentile:.0f}% of their peers."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Percentile", f"{percentile:.0f}th")
c2.metric("Reference group", f"{patient_sex}s {age_lo}–{age_hi}")
c3.metric("Reference n", f"{n_ref:,}")
c4.metric("Group mean delta", f"{deltas.mean():+.2f} yrs")

st.markdown(
    f"<div style='background:#F2F4F8;border-left:4px solid {pct_color};"
    f"padding:16px 20px;border-radius:4px;margin:16px 0;font-size:15px;'>"
    f"{interpretation}</div>",
    unsafe_allow_html=True,
)

# ── Distribution plot ─────────────────────────────────────────────────────────
fig = go.Figure()

# Reference distribution
fig.add_trace(go.Histogram(
    x=deltas, nbinsx=50, name=f"{patient_sex}s {age_lo}–{age_hi} (NHANES)",
    marker_color=NAVY, opacity=0.6,
    histnorm='probability density',
))

# Patient marker
y_max = np.histogram(deltas, bins=50)[0].max() / (len(deltas) * (deltas.max() - deltas.min()) / 50)
fig.add_vline(
    x=patient_delta, line_color=pct_color, line_width=3, line_dash='dash',
    annotation_text=f"Patient ({patient_delta:+.1f} yrs, {percentile:.0f}th pct)",
    annotation_position="top right",
    annotation_font_color=pct_color,
)
fig.add_vline(
    x=0, line_color='gray', line_width=1, line_dash='dot',
    annotation_text="Population mean", annotation_position="top left",
)

# Percentile bands
p25, p75 = np.percentile(deltas, 25), np.percentile(deltas, 75)
fig.add_vrect(x0=p25, x1=p75, fillcolor=TEAL, opacity=0.08,
              annotation_text="Middle 50%", annotation_position="top left")

fig.update_layout(
    title=f'Biological Age Acceleration Distribution — {patient_sex}s {age_lo}–{age_hi} (n={n_ref:,})',
    xaxis_title='PhenoAge Delta (Biological Age Acceleration, years)',
    yaxis_title='Density',
    plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
    showlegend=False, height=400,
)
st.plotly_chart(fig, width='stretch', key='norm_dist')

# ── Population percentile bands ───────────────────────────────────────────────
st.markdown("### Population Percentile Reference Table")
st.caption(f"PhenoAge delta thresholds by percentile for {patient_sex}s aged {age_lo}–{age_hi} in NHANES 2001–2018.")

pct_rows = []
for p in [5, 10, 25, 50, 75, 90, 95]:
    val = np.percentile(deltas, p)
    pct_rows.append({
        'Percentile': f"{p}th",
        'PhenoAge Delta Threshold': f"{val:+.1f} years",
        'Meaning': (
            f"Bottom {p}% of {patient_sex.lower()}s {age_lo}–{age_hi} have delta ≤ {val:+.1f} yrs"
        ),
    })
st.dataframe(pd.DataFrame(pct_rows), width='stretch', key='norm_table')

st.caption(
    "Source: NHANES 2001–2018 public-use files. PhenoAge: Levine et al. 2018. "
    "Percentile ranks computed from NHANES exam-weighted sample within age-sex group."
)
