"""
Patient Analysis - upload a single lab report (or enter values once) and
explore the same patient across three coordinated views.

Tabs:
  1. Biological Age - PhenoAge + delta + 10-yr mortality risk (Levine 2018)
  2. Normative Reference - percentile vs. NHANES age-sex reference cohort
  3. Intervention Simulator - biomarker contribution waterfall + what-if sliders

All three tabs read from a single shared input section at the top of the page,
so values entered (or extracted from PDF) flow into every analysis.
No patient data persists beyond the session.
"""
from __future__ import annotations
import io
import json
import math
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from scipy import stats

from src.bioage import compute_phenoage, bootstrap_phenoage
from src.config import NAVY, GOLD, CORAL, TEAL, NHANES_PARQUET, data_exists

st.set_page_config(page_title="Patient Analysis - INEXION Registry", layout="wide")

# Header
st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Longevity Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Patient Analysis</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Upload one lab report - explore biological age, normative percentile, and
            intervention targets for the same patient
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Shared session state defaults
DEFAULTS = {
    "pa_age":         50,
    "pa_sex":         "Male",
    "pa_albumin":     4.3,
    "pa_creatinine":  0.9,
    "pa_glucose":     95.0,
    "pa_crp":         1.5,
    "pa_lymph":       30.0,
    "pa_mcv":         90.0,
    "pa_rdw":         13.0,
    "pa_alkphos":     70.0,
    "pa_wbc":         6.5,
    "pa_extract_msg": "",
    "pa_extract_ok":  False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# PDF extraction (Claude Haiku)
def extract_labs_from_pdf(pdf_bytes: bytes) -> dict:
    try:
        import pdfplumber
    except ImportError:
        return {"message": "pdfplumber not installed.", "ok": False}
    try:
        import anthropic
    except ImportError:
        return {"message": "anthropic SDK not installed.", "ok": False}

    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
    if not text_pages:
        return {"message": "Could not extract text from this PDF. Try a text-based lab report rather than a scanned image.", "ok": False}

    lab_text = "\n".join(text_pages)[:8000]

    system_prompt = (
        "You are a clinical lab report parser. Extract specific biomarker values from the "
        "provided lab report text and return them as a JSON object. "
        "Return ONLY valid JSON - no explanation, no markdown, no code fences. "
        "If a value is not found or ambiguous, use null. "
        "All values must be in the units specified."
    )
    user_prompt = (
        "Extract the following biomarker values from this lab report.\n"
        "Return a JSON object with exactly these keys and units:\n"
        "{\n"
        '  "albumin":   <float, g/dL>,\n'
        '  "creatinine":<float, mg/dL>,\n'
        '  "glucose":   <float, mg/dL fasting>,\n'
        '  "crp":       <float, mg/L; if reported as mg/dL multiply by 10>,\n'
        '  "lymph":     <float, % lymphocyte>,\n'
        '  "mcv":       <float, fL>,\n'
        '  "rdw":       <float, %>,\n'
        '  "alkphos":   <float, U/L alkaline phosphatase>,\n'
        '  "wbc":       <float, x1000/uL>\n'
        "}\n\n"
        f"Lab report text:\n{lab_text}"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"message": "ANTHROPIC_API_KEY not set in environment.", "ok": False}

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        extracted = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"message": f"Could not parse extraction response: {e}", "ok": False}
    except Exception as e:
        return {"message": f"Extraction error: {e}", "ok": False}

    field_map = {
        "albumin":    ("pa_albumin",    2.5,  6.0),
        "creatinine": ("pa_creatinine", 0.3,  5.0),
        "glucose":    ("pa_glucose",    50.0, 400.0),
        "crp":        ("pa_crp",        0.01, 50.0),
        "lymph":      ("pa_lymph",      5.0,  80.0),
        "mcv":        ("pa_mcv",        70.0, 110.0),
        "rdw":        ("pa_rdw",        10.0, 25.0),
        "alkphos":    ("pa_alkphos",    20.0, 400.0),
        "wbc":        ("pa_wbc",        2.0,  20.0),
    }
    found, missing = [], []
    for key, (state_key, lo, hi) in field_map.items():
        val = extracted.get(key)
        if val is not None:
            try:
                fval = float(val)
                if lo <= fval <= hi:
                    st.session_state[state_key] = fval
                    found.append(key)
                else:
                    missing.append(f"{key} (out of range: {fval})")
            except (TypeError, ValueError):
                missing.append(key)
        else:
            missing.append(key)

    if found:
        msg = f"Extracted {len(found)}/9 values: {', '.join(found)}."
        if missing:
            msg += f" Not found: {', '.join(missing)}. Enter these manually."
        return {"message": msg, "ok": True}
    return {"message": "No biomarker values could be extracted.", "ok": False}


with st.expander("Upload lab report to auto-populate values", expanded=False):
    st.caption(
        "Upload a PDF lab report (Quest, LabCorp, hospital, or equivalent). "
        "Values will be extracted automatically and pre-filled below. "
        "Review values before relying on results."
    )
    uploaded = st.file_uploader("Lab report PDF", type=["pdf"],
                                 label_visibility="collapsed", key="pa_pdf_upload")
    if uploaded is not None:
        with st.spinner("Extracting lab values..."):
            r = extract_labs_from_pdf(uploaded.read())
            st.session_state["pa_extract_msg"] = r["message"]
            st.session_state["pa_extract_ok"]  = r.get("ok", False)
    if st.session_state["pa_extract_msg"]:
        if st.session_state["pa_extract_ok"]:
            st.success(st.session_state["pa_extract_msg"])
        else:
            st.warning(st.session_state["pa_extract_msg"])

st.markdown("### Patient Inputs")
st.caption(
    "These values flow into all three tabs below. "
    "Enter or upload once - explore everywhere."
)

RACE_OPTIONS = ["Non-Hispanic White", "Non-Hispanic Black",
                "Mexican American", "Other Hispanic", "Other / Multi-racial",
                "Prefer not to say"]
RACE_TO_NHANES = {
    "Non-Hispanic White":   3,
    "Non-Hispanic Black":   4,
    "Mexican American":     1,
    "Other Hispanic":       2,
    "Other / Multi-racial": 5,
    "Prefer not to say":    None,
}
if "pa_race" not in st.session_state:
    st.session_state["pa_race"] = "Non-Hispanic White"

dcol, _ = st.columns([1, 2])
with dcol:
    st.number_input("Age (years)", min_value=18, max_value=100, step=1, key="pa_age")
    st.selectbox("Sex", ["Male", "Female"], key="pa_sex",
                 help="Used for normative reference percentile stratification.")
    st.selectbox("Race / Ethnicity", RACE_OPTIONS, key="pa_race",
                 help="Used for matched-cohort reference. 'Prefer not to say' "
                      "falls back to age x sex matching.")

c1, c2, c3 = st.columns(3)
with c1:
    st.number_input("Albumin (g/dL)",             min_value=2.5,  max_value=6.0,   step=0.1, key="pa_albumin")
    st.number_input("Creatinine (mg/dL)",         min_value=0.3,  max_value=5.0,   step=0.1, key="pa_creatinine")
    st.number_input("Glucose (mg/dL)",            min_value=50.0, max_value=400.0, step=1.0, key="pa_glucose")
with c2:
    st.number_input("CRP (mg/L)",                 min_value=0.01, max_value=50.0,  step=0.1, key="pa_crp")
    st.number_input("Lymphocyte %",               min_value=5.0,  max_value=80.0,  step=0.5, key="pa_lymph")
    st.number_input("MCV (fL)",                   min_value=70.0, max_value=110.0, step=0.5, key="pa_mcv")
with c3:
    st.number_input("RDW (%)",                    min_value=10.0, max_value=25.0,  step=0.1, key="pa_rdw")
    st.number_input("Alkaline phosphatase (U/L)", min_value=20.0, max_value=400.0, step=1.0, key="pa_alkphos")
    st.number_input("WBC (x1000/uL)",             min_value=2.0,  max_value=20.0,  step=0.1, key="pa_wbc")

age      = st.session_state["pa_age"]
sex      = st.session_state["pa_sex"]
albumin  = st.session_state["pa_albumin"]
creatinine = st.session_state["pa_creatinine"]
glucose  = st.session_state["pa_glucose"]
crp      = st.session_state["pa_crp"]
lymph    = st.session_state["pa_lymph"]
mcv      = st.session_state["pa_mcv"]
rdw      = st.session_state["pa_rdw"]
alkphos  = st.session_state["pa_alkphos"]
wbc      = st.session_state["pa_wbc"]

pa_result = compute_phenoage(
    age=age, albumin_g_dl=albumin, creatinine_mg_dl=creatinine,
    glucose_mg_dl=glucose, crp_mg_l=crp, lymphocyte_pct=lymph,
    mcv_fl=mcv, rdw_pct=rdw, alk_phos_u_l=alkphos, wbc_1000_ul=wbc,
)
phenoage  = pa_result["phenoage"]
delta     = pa_result["delta"]
mortality = pa_result["mortality_10y"]

# Bootstrap measurement-error CIs - cached on the input tuple
@st.cache_data(show_spinner=False)
def _phenoage_input_corr():
    """Empirical 9x9 correlation matrix among PhenoAge inputs (CRP in log)."""
    if not data_exists(NHANES_PARQUET):
        return None
    cols = ['albumin','creatinine','glucose_biopro','crp','lymphocyte_pct',
            'mcv','rdw','alkaline_phosphatase','wbc']
    ref_df = pd.read_parquet(NHANES_PARQUET, columns=cols).dropna()
    ref_df['crp'] = np.log(ref_df['crp'].clip(lower=0.01))
    return ref_df.corr().to_numpy()

_PA_CORR = _phenoage_input_corr()

@st.cache_data(show_spinner=False)
def _boot_ci(age, albumin, creatinine, glucose, crp, lymph,
             mcv, rdw, alkphos, wbc, n_boot=1000):
    return bootstrap_phenoage(
        age, albumin, creatinine, glucose, crp, lymph,
        mcv, rdw, alkphos, wbc, n_boot=n_boot,
        corr_matrix=_PA_CORR,
    )

ci = _boot_ci(age, albumin, creatinine, glucose, crp, lymph,
              mcv, rdw, alkphos, wbc)

st.markdown("---")

tabs = st.tabs(["Biological Age", "Normative Reference", "Intervention Simulator"])

# TAB 1 - BIOLOGICAL AGE
with tabs[0]:
    delta_color = TEAL if delta <= 0 else CORAL
    delta_label = "biologically younger" if delta <= 0 else "biologically older"

    st.markdown(
        f"""
        <div style='background:{NAVY}; color:white; padding:28px;
                    border-radius:10px; text-align:center; margin-top:8px;'>
            <div style='color:{GOLD}; font-size:12px; letter-spacing:2px;
                        text-transform:uppercase;'>PhenoAge result</div>
            <div style='font-size:56px; font-weight:800; margin-top:6px;'>
                {phenoage:.1f} <span style='color:{GOLD}; font-size:28px;'>years</span>
            </div>
            <div style='font-size:14px; color:#C9CBD4; margin-top:4px;'>
                95% CI [{ci['phenoage_lo']:.1f}, {ci['phenoage_hi']:.1f}]
                &nbsp;-&nbsp; analytical measurement-error bootstrap, n={ci['n_boot']}
            </div>
            <div style='font-size:18px; color:{delta_color}; margin-top:14px; font-weight:600;'>
                {delta:+.1f} years - {delta_label} than chronological age
            </div>
            <div style='font-size:14px; color:#C9CBD4; margin-top:4px;'>
                95% CI [{ci['delta_lo']:+.1f}, {ci['delta_hi']:+.1f}] years
            </div>
            <div style='font-size:13px; color:#C9CBD4; margin-top:14px;'>
                Estimated 10-year mortality risk (Gompertz):
                {mortality * 100:.2f}%
                &nbsp;[{ci['mort_lo']*100:.2f}%, {ci['mort_hi']*100:.2f}%]
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    fig_ci = go.Figure()
    fig_ci.add_trace(go.Scatter(
        x=[ci['delta_lo'], ci['delta_hi']], y=[0, 0],
        mode='lines',
        line=dict(color=NAVY, width=8),
        name='95% measurement-error CI',
    ))
    fig_ci.add_trace(go.Scatter(
        x=[delta], y=[0],
        mode='markers',
        marker=dict(color=GOLD, size=18, line=dict(color=NAVY, width=2)),
        name='Point estimate',
    ))
    fig_ci.add_vline(x=0, line_dash='dash', line_color='gray',
                     annotation_text='Chronological = biological',
                     annotation_position='top')
    pad = max(2.0, abs(delta) * 0.5)
    fig_ci.update_layout(
        height=140,
        plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
        showlegend=False,
        xaxis=dict(
            title='PhenoAge delta (years younger / older than chronological age)',
            range=[min(ci['delta_lo'], -pad) - 1, max(ci['delta_hi'], pad) + 1],
            zeroline=False,
        ),
        yaxis=dict(visible=False, range=[-1, 1]),
        margin=dict(t=10, b=40, l=20, r=20),
    )
    st.plotly_chart(fig_ci, use_container_width=True, key='pa_delta_ci')

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=["Chronological", "Biological (PhenoAge)"],
        x=[age, phenoage],
        orientation="h",
        marker_color=[GOLD, NAVY],
        text=[f"{age} yr", f"{phenoage:.1f} yr"],
        textposition="outside",
    ))
    fig.update_layout(
        height=220, plot_bgcolor="white", paper_bgcolor="white",
        font_color="#1A1A2E", showlegend=False,
        xaxis=dict(range=[0, max(age, phenoage) * 1.25], title="Age (years)"),
        margin=dict(t=20, b=40, l=40, r=40),
    )
    st.plotly_chart(fig, use_container_width=True, key="pa_bar_bioage")

    st.caption(
        "PhenoAge is a research instrument validated on NHANES population data (Levine et al., 2018). "
        "It is not a clinical diagnostic. A +3 year delta means biomarkers statistically resemble "
        "those of a 3-year-older population mean - not that any individual 'is' biologically 3 years older. "
        "95% CIs are Monte-Carlo bootstrap (n=1000) using CAP/CLIA analytical CVs - "
        "they reflect lab measurement noise on a re-draw, not population variability."
    )

# TAB 2 - NORMATIVE REFERENCE
with tabs[1]:
    @st.cache_data
    def load_reference():
        if not data_exists(NHANES_PARQUET):
            return pd.DataFrame()
        df = pd.read_parquet(NHANES_PARQUET,
            columns=['age','sex','race_ethnicity','phenoage_delta',
                     'phenoage','exam_weight_adj'])
        df = df[df['phenoage_delta'].notna() & df['age'].between(20, 85)].copy()
        df['sex_label'] = df['sex'].map({1:'Male', 2:'Female'})
        return df

    ref = load_reference()
    if ref.empty:
        st.warning("NHANES reference parquet not found - normative percentile unavailable.")
    else:
        age_for_match = max(20, min(85, age))
        age_bin = (age_for_match // 10) * 10
        age_bin = max(20, min(80, age_bin))
        age_lo, age_hi = age_bin, age_bin + 9
        sex_code = 1 if sex == "Male" else 2
        race_code = RACE_TO_NHANES.get(st.session_state.get("pa_race",
                                                              "Prefer not to say"))

        # Try age x sex x race first; fall back to age x sex if race subgroup
        # is too small (n<50) or user chose "Prefer not to say"
        match_used = "age x sex x race"
        ref_cohort = ref[
            ref['age'].between(age_lo, age_hi) &
            (ref['sex'] == sex_code) &
            ref['phenoage_delta'].notna()
        ]
        if race_code is not None:
            attempt = ref_cohort[ref_cohort.get('race_ethnicity') == race_code]
            if len(attempt) >= 50:
                ref_cohort = attempt
            else:
                match_used = "age x sex (race subgroup n<50)"
        else:
            match_used = "age x sex (race not provided)"

        # If still too small, widen age window
        if len(ref_cohort) < 50:
            ref_cohort = ref[
                ref['age'].between(max(20, age_lo - 10), min(85, age_hi + 10)) &
                (ref['sex'] == sex_code) &
                ref['phenoage_delta'].notna()
            ]
            match_used = "age decade widened x sex (small original cell)"

        n_ref = len(ref_cohort)
        deltas = ref_cohort['phenoage_delta'].values

        # Survey-weighted percentile (Kish-style) using exam_weight_adj
        from src.stats import weighted_quantile
        if 'exam_weight_adj' in ref_cohort.columns and ref_cohort['exam_weight_adj'].notna().any():
            weights = ref_cohort['exam_weight_adj'].values
            # Walk percentiles 1..99 to find the patient's percentile
            qs = np.linspace(0.01, 0.99, 99)
            edges = np.array([weighted_quantile(deltas, q, weights) for q in qs])
            percentile = float(np.searchsorted(edges, delta, side='right'))
            percentile = float(np.clip(percentile, 0, 100))
        else:
            percentile = float(stats.percentileofscore(deltas, delta, kind='rank'))

        pct_color = CORAL if percentile > 75 else (TEAL if percentile < 25 else GOLD)
        direction = "faster" if delta > 0 else "slower"
        interpretation = (
            f"This patient's biomarkers resemble those of someone biologically "
            f"{abs(delta):.1f} years {'older' if delta > 0 else 'younger'} "
            f"than their chronological age. Among {sex.lower()}s aged {age_lo}-{age_hi} "
            f"in the U.S. population (NHANES 2001-2018, n={n_ref:,}), this patient is at the "
            f"**{percentile:.0f}th percentile** of biological age acceleration - aging "
            f"{direction} than {100 - percentile:.0f}% of their peers."
        )

        race_label = st.session_state.get("pa_race", "—")
        cA, cB, cC, cD = st.columns(4)
        cA.metric("Percentile", f"{percentile:.0f}th")
        cB.metric("Reference group",
                   f"{race_label} {sex.lower()}s {age_lo}-{age_hi}"
                   if "race" in match_used else f"{sex}s {age_lo}-{age_hi}")
        cC.metric("Reference n", f"{n_ref:,}")
        cD.metric("Group mean delta", f"{deltas.mean():+.2f} yrs")
        st.caption(f"Match: {match_used}. Percentile is survey-weighted (NHANES exam_weight_adj).")

        st.markdown(
            f"<div style='background:#F2F4F8;border-left:4px solid {pct_color};"
            f"padding:16px 20px;border-radius:4px;margin:16px 0;font-size:15px;'>"
            f"{interpretation}</div>",
            unsafe_allow_html=True,
        )

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=deltas, nbinsx=50,
            name=f"{sex}s {age_lo}-{age_hi} (NHANES)",
            marker_color=NAVY, opacity=0.6,
            histnorm='probability density',
        ))
        fig.add_vline(
            x=delta, line_color=pct_color, line_width=3, line_dash='dash',
            annotation_text=f"Patient ({delta:+.1f} yrs, {percentile:.0f}th pct)",
            annotation_position="top right", annotation_font_color=pct_color,
        )
        fig.add_vline(
            x=0, line_color='gray', line_width=1, line_dash='dot',
            annotation_text="Population mean", annotation_position="top left",
        )
        p25, p75 = np.percentile(deltas, 25), np.percentile(deltas, 75)
        fig.add_vrect(x0=p25, x1=p75, fillcolor=TEAL, opacity=0.08,
                      annotation_text="Middle 50%", annotation_position="top left")
        fig.update_layout(
            title=f'Biological Age Acceleration Distribution - {sex}s {age_lo}-{age_hi} (n={n_ref:,})',
            xaxis_title='PhenoAge Delta (years)',
            yaxis_title='Density',
            plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
            showlegend=False, height=380,
        )
        st.plotly_chart(fig, use_container_width=True, key="pa_norm_dist")

        st.markdown("##### Population percentile reference table")
        pct_rows = []
        for p in [5, 10, 25, 50, 75, 90, 95]:
            val = float(np.percentile(deltas, p))
            pct_rows.append({
                'Percentile': f"{p}th",
                'PhenoAge Delta Threshold': f"{val:+.1f} years",
                'Meaning': f"Bottom {p}% have delta <= {val:+.1f} yrs",
            })
        st.dataframe(pd.DataFrame(pct_rows), use_container_width=True,
                     hide_index=True, key="pa_pct_table")

# TAB 3 - INTERVENTION SIMULATOR
with tabs[2]:
    COEFFS = {
        'albumin':    -0.03359355,
        'creatinine':  0.009506491,
        'glucose':     0.1953192,
        'ln_crp':      0.09536762,
        'lymph_pct':  -0.01199984,
        'mcv':         0.02676401,
        'rdw':         0.3306156,
        'alkphos':     0.001868778,
        'wbc':         0.05542406,
    }

    @st.cache_data
    def load_reference_means():
        if not data_exists(NHANES_PARQUET):
            return None, None
        df = pd.read_parquet(NHANES_PARQUET,
            columns=['albumin','creatinine','glucose_biopro','ln_crp',
                     'lymphocyte_pct','mcv','rdw','alkaline_phosphatase','wbc'])
        means = {
            'albumin_si':    (df['albumin'].dropna() * 10).mean(),
            'creatinine_si': (df['creatinine'].dropna() * 88.4).mean(),
            'glucose_si':    (df['glucose_biopro'].dropna() / 18.02).mean(),
            'ln_crp':        df['ln_crp'].dropna().mean(),
            'lymph_pct':     df['lymphocyte_pct'].dropna().mean(),
            'mcv':           df['mcv'].dropna().mean(),
            'rdw':           df['rdw'].dropna().mean(),
            'alkphos':       df['alkaline_phosphatase'].dropna().mean(),
            'wbc':           df['wbc'].dropna().mean(),
        }
        ranges = {
            'albumin_gdl':     (df['albumin'].quantile(0.02), df['albumin'].quantile(0.98)),
            'creatinine_mgdl': (df['creatinine'].quantile(0.02), df['creatinine'].quantile(0.98)),
            'glucose_mgdl':    (df['glucose_biopro'].quantile(0.02), min(400.0, df['glucose_biopro'].quantile(0.98))),
            'crp_mgl':         ((np.exp(df['ln_crp'])).quantile(0.02), min(50.0, (np.exp(df['ln_crp'])).quantile(0.98))),
            'lymph_pct':       (df['lymphocyte_pct'].quantile(0.02), df['lymphocyte_pct'].quantile(0.98)),
            'mcv':             (df['mcv'].quantile(0.02), df['mcv'].quantile(0.98)),
            'rdw':             (df['rdw'].quantile(0.02), df['rdw'].quantile(0.98)),
            'alkphos':         (df['alkaline_phosphatase'].quantile(0.02), min(400.0, df['alkaline_phosphatase'].quantile(0.98))),
            'wbc':             (df['wbc'].quantile(0.02), df['wbc'].quantile(0.98)),
        }
        return means, ranges

    ref_means, ref_ranges = load_reference_means()
    if ref_means is None:
        st.warning("NHANES reference parquet not found - intervention simulator unavailable.")
    else:
        def contributions(albumin_gdl, creatinine_mgdl, glucose_mgdl,
                           crp_mgl, lymph_pct, mcv_, rdw_, alkphos_, wbc_):
            patient = {
                'albumin_si':    albumin_gdl * 10.0,
                'creatinine_si': creatinine_mgdl * 88.4,
                'glucose_si':    glucose_mgdl / 18.02,
                'ln_crp':        math.log(max(crp_mgl, 0.01)),
                'lymph_pct':     lymph_pct,
                'mcv':           mcv_,
                'rdw':           rdw_,
                'alkphos':       alkphos_,
                'wbc':           wbc_,
            }
            coeff_map = {
                'albumin_si':    COEFFS['albumin'],
                'creatinine_si': COEFFS['creatinine'],
                'glucose_si':    COEFFS['glucose'],
                'ln_crp':        COEFFS['ln_crp'],
                'lymph_pct':     COEFFS['lymph_pct'],
                'mcv':           COEFFS['mcv'],
                'rdw':           COEFFS['rdw'],
                'alkphos':       COEFFS['alkphos'],
                'wbc':           COEFFS['wbc'],
            }
            label_map = {
                'albumin_si': 'Albumin', 'creatinine_si': 'Creatinine',
                'glucose_si': 'Glucose', 'ln_crp': 'CRP',
                'lymph_pct': 'Lymphocyte %', 'mcv': 'MCV',
                'rdw': 'RDW', 'alkphos': 'Alkaline Phosphatase', 'wbc': 'WBC',
            }
            return {label_map[k]: coeff_map[k] * (patient[k] - ref_means[k])
                    for k in coeff_map}

        st.markdown("##### Current biomarker contributions to biological age acceleration")
        st.caption(
            "How much each biomarker is adding to or subtracting from this patient's biological age, "
            "relative to the U.S. population mean for each biomarker."
        )
        contribs = contributions(albumin, creatinine, glucose, crp, lymph, mcv, rdw, alkphos, wbc)
        contrib_df = pd.DataFrame([
            {'Biomarker': k, 'Contribution (yrs)': v}
            for k, v in sorted(contribs.items(), key=lambda x: x[1], reverse=True)
        ])
        colors = [CORAL if v > 0 else TEAL for v in contrib_df['Contribution (yrs)']]
        fig = go.Figure(go.Bar(
            x=contrib_df['Contribution (yrs)'],
            y=contrib_df['Biomarker'],
            orientation='h',
            marker_color=colors,
            text=[f"{v:+.3f}" for v in contrib_df['Contribution (yrs)']],
            textposition='outside',
        ))
        fig.add_vline(x=0, line_color='gray', line_width=1)
        fig.update_layout(
            xaxis_title='Contribution to PhenoAge Delta (years)',
            plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
            height=360, margin=dict(l=150, t=10, b=40, r=20),
        )
        st.plotly_chart(fig, use_container_width=True, key="pa_contrib_bar")

        positive = contrib_df[contrib_df['Contribution (yrs)'] > 0].head(3)
        if len(positive) > 0:
            names = ', '.join(positive['Biomarker'].tolist())
            total_reducible = positive['Contribution (yrs)'].sum()
            st.info(
                f"**Highest-impact targets:** {names}. "
                f"Optimizing these three biomarkers to population median could reduce "
                f"biological age by up to **{total_reducible:.1f} years** for this patient."
            )

        st.markdown("##### Simulate interventions")
        st.caption(
            "Adjust biomarker values to model what-if outcomes. "
            "Sliders default to the patient's current values from the inputs above."
        )

        slider_init = {
            "sl_alb": albumin, "sl_crt": creatinine, "sl_glc": glucose,
            "sl_crp": crp, "sl_lym": lymph, "sl_mcv": mcv,
            "sl_rdw": rdw, "sl_alp": alkphos, "sl_wbc": wbc,
        }
        baseline_sig = (albumin, creatinine, glucose, crp, lymph, mcv, rdw, alkphos, wbc)
        if st.session_state.get("pa_sim_baseline_sig") != baseline_sig:
            for k, v in slider_init.items():
                st.session_state[k] = float(v)
            st.session_state["pa_sim_baseline_sig"] = baseline_sig

        s1, s2, s3 = st.columns(3)
        with s1:
            sim_albumin = st.slider(
                "Albumin (g/dL)",
                min_value=float(max(2.5, ref_ranges['albumin_gdl'][0])),
                max_value=float(min(6.0, ref_ranges['albumin_gdl'][1])),
                step=0.1, key="sl_alb",
            )
            sim_creatinine = st.slider(
                "Creatinine (mg/dL)",
                min_value=float(max(0.3, ref_ranges['creatinine_mgdl'][0])),
                max_value=float(min(5.0, ref_ranges['creatinine_mgdl'][1])),
                step=0.1, key="sl_crt",
            )
            sim_glucose = st.slider(
                "Glucose (mg/dL)",
                min_value=float(max(50.0, ref_ranges['glucose_mgdl'][0])),
                max_value=float(min(400.0, ref_ranges['glucose_mgdl'][1])),
                step=1.0, key="sl_glc",
            )
        with s2:
            sim_crp = st.slider(
                "CRP (mg/L)",
                min_value=float(max(0.01, ref_ranges['crp_mgl'][0])),
                max_value=float(min(50.0, ref_ranges['crp_mgl'][1])),
                step=0.1, key="sl_crp",
            )
            sim_lymph = st.slider(
                "Lymphocyte %",
                min_value=float(max(5.0, ref_ranges['lymph_pct'][0])),
                max_value=float(min(80.0, ref_ranges['lymph_pct'][1])),
                step=0.5, key="sl_lym",
            )
            sim_mcv = st.slider(
                "MCV (fL)",
                min_value=float(max(70.0, ref_ranges['mcv'][0])),
                max_value=float(min(110.0, ref_ranges['mcv'][1])),
                step=0.5, key="sl_mcv",
            )
        with s3:
            sim_rdw = st.slider(
                "RDW (%)",
                min_value=float(max(10.0, ref_ranges['rdw'][0])),
                max_value=float(min(25.0, ref_ranges['rdw'][1])),
                step=0.1, key="sl_rdw",
            )
            sim_alkphos = st.slider(
                "Alkaline Phosphatase (U/L)",
                min_value=float(max(20.0, ref_ranges['alkphos'][0])),
                max_value=float(min(400.0, ref_ranges['alkphos'][1])),
                step=1.0, key="sl_alp",
            )
            sim_wbc = st.slider(
                "WBC (x1000/uL)",
                min_value=float(max(2.0, ref_ranges['wbc'][0])),
                max_value=float(min(20.0, ref_ranges['wbc'][1])),
                step=0.1, key="sl_wbc",
            )

        sim_result = compute_phenoage(
            age=age, albumin_g_dl=sim_albumin, creatinine_mg_dl=sim_creatinine,
            glucose_mg_dl=sim_glucose, crp_mg_l=sim_crp, lymphocyte_pct=sim_lymph,
            mcv_fl=sim_mcv, rdw_pct=sim_rdw, alk_phos_u_l=sim_alkphos, wbc_1000_ul=sim_wbc,
        )
        delta_sim = sim_result["delta"]
        improvement = delta - delta_sim
        imp_color = TEAL if improvement > 0 else CORAL
        sign = "-" if improvement > 0 else "+"

        sim_ci = _boot_ci(age, sim_albumin, sim_creatinine, sim_glucose, sim_crp,
                          sim_lymph, sim_mcv, sim_rdw, sim_alkphos, sim_wbc, n_boot=500)

        st.markdown(
            f"<div style='background:#F2F4F8;border-left:4px solid {imp_color};"
            f"padding:16px 20px;border-radius:4px;margin:16px 0;'>"
            f"<div style='font-size:14px;color:#1A1A2E;'>"
            f"<strong>Simulated PhenoAge delta:</strong> "
            f"<span style='color:{imp_color};font-size:20px;font-weight:700;'>{delta_sim:+.1f} years</span>"
            f"&nbsp;<span style='color:#6B7280;font-size:13px;'>"
            f"[CI {sim_ci['delta_lo']:+.1f}, {sim_ci['delta_hi']:+.1f}]</span>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<strong>Change from baseline:</strong> "
            f"<span style='color:{imp_color};font-size:20px;font-weight:700;'>{sign}{abs(improvement):.1f} years</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        # Phase 7.3 - dual-CI plot: baseline vs simulated delta with CI bands
        fig_ci = go.Figure()
        # Baseline CI
        fig_ci.add_trace(go.Scatter(
            x=[ci['delta_lo'], ci['delta_hi']], y=[1, 1],
            mode='lines', line=dict(color=NAVY, width=10),
            name='Baseline 95% CI', showlegend=True,
        ))
        fig_ci.add_trace(go.Scatter(
            x=[delta], y=[1],
            mode='markers', marker=dict(color=GOLD, size=18,
                                          line=dict(color=NAVY, width=2)),
            name='Baseline point', showlegend=False,
        ))
        # Simulated CI
        fig_ci.add_trace(go.Scatter(
            x=[sim_ci['delta_lo'], sim_ci['delta_hi']], y=[0, 0],
            mode='lines', line=dict(color=imp_color, width=10),
            name='Simulated 95% CI', showlegend=True,
        ))
        fig_ci.add_trace(go.Scatter(
            x=[delta_sim], y=[0],
            mode='markers', marker=dict(color=GOLD, size=18,
                                          line=dict(color=imp_color, width=2)),
            name='Simulated point', showlegend=False,
        ))
        fig_ci.add_vline(x=0, line_dash='dash', line_color='gray',
                          annotation_text='No advance', annotation_position='top')
        # Shaded "meaningful change" zone if simulated CI does NOT overlap baseline CI
        no_overlap = (sim_ci['delta_hi'] < ci['delta_lo']) or (sim_ci['delta_lo'] > ci['delta_hi'])
        verdict = ("Simulated CI does NOT overlap baseline CI - change exceeds lab noise."
                   if no_overlap else
                   "Simulated CI overlaps baseline CI - change is within lab noise.")
        pad = max(2.0, abs(delta) * 0.5, abs(delta_sim) * 0.5)
        x_lo = min(ci['delta_lo'], sim_ci['delta_lo']) - 1
        x_hi = max(ci['delta_hi'], sim_ci['delta_hi']) + 1
        fig_ci.update_layout(
            height=180, plot_bgcolor='white', paper_bgcolor='white',
            font_color='#1A1A2E',
            xaxis=dict(title='PhenoAge delta (years)',
                        range=[min(x_lo, -pad), max(x_hi, pad)], zeroline=False),
            yaxis=dict(visible=False, range=[-0.5, 1.5],
                        tickvals=[0, 1], ticktext=['Simulated', 'Baseline']),
            yaxis_showticklabels=True,
            margin=dict(t=10, b=40, l=80, r=20),
            legend=dict(orientation='h', y=-0.25),
        )
        st.plotly_chart(fig_ci, use_container_width=True, key='pa_dual_ci')
        st.caption(verdict)

        st.caption(
            "PhenoAge: Levine et al., Aging Cell 2018. Contributions computed as "
            "coefficient * (patient_value - NHANES population mean). "
            "Simulated delta CI uses the same n=500 measurement-error bootstrap as Tab 1, "
            "with the empirical NHANES correlation matrix among the 9 inputs. "
            "This tool is for research and clinical exploration - not a diagnostic instrument."
        )
