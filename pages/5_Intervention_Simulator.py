"""
Intervention Simulator — which biomarker moves the needle most?

Shows biomarker contributions to PhenoAge acceleration and lets users
simulate the effect of improving individual biomarkers. Answers the
clinical question: where should I focus treatment first?
"""
import streamlit as st
import pandas as pd
import numpy as np
import math
import io, json, os
import plotly.graph_objects as go
import plotly.express as px
from src.config import NAVY, GOLD, CORAL, TEAL, NHANES_PARQUET

st.set_page_config(page_title="Intervention Simulator — INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Intervention Simulator</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Which biomarker moves the needle most? · PhenoAge marginal contribution analysis
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── PhenoAge algorithm constants ──────────────────────────────────────────────
COEFFS = {
    'albumin':    -0.03359355,   # per g/L (input g/dL × 10)
    'creatinine':  0.009506491,  # per µmol/L (input mg/dL × 88.4)
    'glucose':     0.1953192,    # per mmol/L (input mg/dL ÷ 18.02)
    'ln_crp':      0.09536762,   # per ln(mg/L)
    'lymph_pct':  -0.01199984,   # per %
    'mcv':         0.02676401,   # per fL
    'rdw':         0.3306156,    # per %
    'alkphos':     0.001868778,  # per U/L
    'wbc':         0.05542406,   # per 1000/µL
}
INTERCEPT = -19.90667
GOMPERTZ_GAMMA = -1.51714
GOMPERTZ_DIV   = 0.007692696
PA_MORT_COEFF  = -0.0055305
PA_AGE_DIV     = 0.090165
PA_CONSTANT    = 141.50225

# NHANES reference means for each biomarker (used to compute contributions)
@st.cache_data
def load_reference_means():
    df = pd.read_parquet(NHANES_PARQUET,
        columns=['albumin','creatinine','glucose_biopro','ln_crp',
                 'lymphocyte_pct','mcv','rdw','alkaline_phosphatase','wbc'])
    # glucose_biopro is stored in mg/dL — convert to mmol/L for SI reference mean
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
    # Reference ranges for sliders (in clinical/input units)
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

def compute_pa(age, albumin_gdl, creatinine_mgdl, glucose_mgdl,
               crp_mgl, lymph_pct, mcv, rdw, alkphos, wbc):
    alb_si  = albumin_gdl * 10.0
    crt_si  = creatinine_mgdl * 88.4
    glc_si  = glucose_mgdl / 18.02
    ln_crp  = math.log(max(crp_mgl, 0.01))
    xb = (INTERCEPT
        + COEFFS['albumin']    * alb_si
        + COEFFS['creatinine'] * crt_si
        + COEFFS['glucose']    * glc_si
        + COEFFS['ln_crp']     * ln_crp
        + COEFFS['lymph_pct']  * lymph_pct
        + COEFFS['mcv']        * mcv
        + COEFFS['rdw']        * rdw
        + COEFFS['alkphos']    * alkphos
        + COEFFS['wbc']        * wbc
        + 0.08035356           * age)
    m = 1.0 - math.exp((GOMPERTZ_GAMMA * math.exp(xb)) / GOMPERTZ_DIV)
    m = min(max(m, 1e-10), 1 - 1e-10)
    pa = math.log(PA_MORT_COEFF * math.log(1 - m)) / PA_AGE_DIV + PA_CONSTANT
    return pa

def si_contributions(albumin_gdl, creatinine_mgdl, glucose_mgdl,
                     crp_mgl, lymph_pct, mcv, rdw, alkphos, wbc):
    """Return weighted contribution of each biomarker to xb (relative to population mean)."""
    patient = {
        'albumin_si':    albumin_gdl * 10,
        'creatinine_si': creatinine_mgdl * 88.4,
        'glucose_si':    glucose_mgdl / 18.02,
        'ln_crp':        math.log(max(crp_mgl, 0.01)),
        'lymph_pct':     lymph_pct,
        'mcv':           mcv,
        'rdw':           rdw,
        'alkphos':       alkphos,
        'wbc':           wbc,
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
    contribs = {}
    for key, coeff in coeff_map.items():
        delta_from_mean = patient[key] - ref_means[key]
        contribs[label_map[key]] = coeff * delta_from_mean
    return contribs

# ── PDF extraction ────────────────────────────────────────────────────────────
def extract_labs_for_simulator(pdf_bytes: bytes) -> dict:
    try:
        import pdfplumber, anthropic
    except ImportError as e:
        return {"message": f"Missing dependency: {e}", "ok": False}

    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
    if not text_pages:
        return {"message": "Could not extract text. Try a text-based PDF.", "ok": False}

    lab_text = "\n".join(text_pages)[:8000]
    system_prompt = (
        "You are a clinical lab report parser. Extract specific biomarker values "
        "and return ONLY valid JSON — no explanation, no markdown, no code fences. "
        "Use null for missing values."
    )
    user_prompt = f"""Extract these biomarker values:
{{"albumin": <float g/dL>, "creatinine": <float mg/dL>, "glucose": <float mg/dL fasting>,
  "crp": <float mg/L>, "lymph": <float % lymphocyte>, "mcv": <float fL>,
  "rdw": <float %>, "alkphos": <float U/L alkaline phosphatase>, "wbc": <float x1000/uL>}}
Lab text:\n{lab_text}"""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"message": "ANTHROPIC_API_KEY not set in environment.", "ok": False}

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"): raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"): raw = "\n".join(raw.split("\n")[:-1])
        extracted = json.loads(raw)
    except Exception as e:
        return {"message": f"Extraction error: {e}", "ok": False}

    # Map to simulator session state keys
    field_map = {
        "albumin":  ("sim_alb",  2.5,  6.0),
        "creatinine": ("sim_crt", 0.3,  5.0),
        "glucose":  ("sim_glc",  50.0, 400.0),
        "crp":      ("sim_crp",  0.01, 50.0),
        "lymph":    ("sim_lym",  5.0,  80.0),
        "mcv":      ("sim_mcv",  70.0, 110.0),
        "rdw":      ("sim_rdw",  10.0, 25.0),
        "alkphos":  ("sim_alp",  20.0, 400.0),
        "wbc":      ("sim_wbc",  2.0,  20.0),
    }
    found, missing = [], []
    for key, (state_key, lo, hi) in field_map.items():
        val = extracted.get(key)
        if val is not None:
            try:
                val = float(val)
                if lo <= val <= hi:
                    st.session_state[state_key] = val
                    found.append(key)
                else:
                    missing.append(f"{key} (out of range: {val})")
            except (TypeError, ValueError):
                missing.append(key)
        else:
            missing.append(key)

    if found:
        msg = f"Extracted {len(found)}/9 values: {', '.join(found)}."
        if missing:
            msg += f" Not found: {', '.join(missing)}. Enter manually."
        return {"message": msg, "ok": True}
    return {"message": "No values extracted. Enter manually.", "ok": False}


# ── Lab report upload ─────────────────────────────────────────────────────────
if "sim_extract_msg" not in st.session_state:
    st.session_state["sim_extract_msg"] = ""
    st.session_state["sim_extract_ok"] = False

with st.expander("📄 Upload lab report to auto-populate values", expanded=False):
    st.caption(
        "Upload a PDF lab report (Quest, LabCorp, hospital, or equivalent). "
        "Values will be extracted and pre-filled below."
    )
    uploaded = st.file_uploader("Lab report PDF", type=["pdf"],
                                label_visibility="collapsed", key="sim_pdf_upload")
    if uploaded is not None:
        with st.spinner("Extracting lab values…"):
            result = extract_labs_for_simulator(uploaded.read())
            st.session_state["sim_extract_msg"] = result["message"]
            st.session_state["sim_extract_ok"]  = result.get("ok", False)
    if st.session_state["sim_extract_msg"]:
        if st.session_state["sim_extract_ok"]:
            st.success(st.session_state["sim_extract_msg"])
        else:
            st.warning(st.session_state["sim_extract_msg"])

st.divider()

# ── Patient input ─────────────────────────────────────────────────────────────
st.markdown("### Current Patient Biomarkers")
st.caption("Enter current values. The simulator shows which biomarkers are aging this patient fastest and what happens if they improve.")

# Initialise defaults only once
for k, v in [("sim_alb",4.1),("sim_crt",0.9),("sim_glc",100.0),("sim_crp",2.0),
             ("sim_lym",28.0),("sim_mcv",90.0),("sim_rdw",13.5),("sim_alp",72.0),("sim_wbc",6.5)]:
    if k not in st.session_state:
        st.session_state[k] = v

c1, c2, c3 = st.columns(3)
with c1:
    age     = st.number_input("Age (years)", 20, 90, 55)
    albumin = st.number_input("Albumin (g/dL)", 2.5, 6.0, st.session_state["sim_alb"], step=0.1, key="sim_alb")
    creatinine = st.number_input("Creatinine (mg/dL)", 0.3, 5.0, st.session_state["sim_crt"], step=0.1, key="sim_crt")
with c2:
    glucose = st.number_input("Glucose (mg/dL)", 50.0, 400.0, st.session_state["sim_glc"], step=1.0, key="sim_glc")
    crp     = st.number_input("CRP (mg/L)", 0.01, 50.0, st.session_state["sim_crp"], step=0.1, key="sim_crp")
    lymph   = st.number_input("Lymphocyte %", 5.0, 80.0, st.session_state["sim_lym"], step=0.5, key="sim_lym")
with c3:
    mcv     = st.number_input("MCV (fL)", 70.0, 110.0, st.session_state["sim_mcv"], step=0.5, key="sim_mcv")
    rdw     = st.number_input("RDW (%)", 10.0, 25.0, st.session_state["sim_rdw"], step=0.1, key="sim_rdw")
    alkphos = st.number_input("Alkaline Phosphatase (U/L)", 20.0, 400.0, st.session_state["sim_alp"], step=1.0, key="sim_alp")
    wbc     = st.number_input("WBC (×1000/µL)", 2.0, 20.0, st.session_state["sim_wbc"], step=0.1, key="sim_wbc")

pa_current = compute_pa(age, albumin, creatinine, glucose, crp, lymph, mcv, rdw, alkphos, wbc)
delta_current = pa_current - age

# ── Current result ────────────────────────────────────────────────────────────
delta_color = CORAL if delta_current > 0 else TEAL
st.markdown(
    f"<div style='background:{NAVY};color:white;padding:20px 28px;border-radius:10px;"
    f"text-align:center;margin:16px 0;'>"
    f"<div style='color:{GOLD};font-size:11px;letter-spacing:2px;text-transform:uppercase;'>"
    f"Current PhenoAge</div>"
    f"<div style='font-size:52px;font-weight:800;margin-top:6px;'>"
    f"<span style='color:{delta_color};'>{delta_current:+.1f}</span>"
    f"<span style='color:{GOLD};font-size:24px;'> years</span></div>"
    f"<div style='font-size:14px;color:#C9CBD4;margin-top:8px;'>"
    f"PhenoAge {pa_current:.1f} · Chronological age {age}</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Biomarker contribution chart ──────────────────────────────────────────────
st.markdown("### Biomarker Contributions to Biological Age Acceleration")
st.caption("How much each biomarker is adding to or subtracting from this patient's biological age, relative to the U.S. population mean for each biomarker.")

contribs = si_contributions(albumin, creatinine, glucose, crp, lymph, mcv, rdw, alkphos, wbc)
contrib_df = pd.DataFrame([
    {'Biomarker': k, 'Contribution (PhenoAge years)': v,
     'Direction': 'Accelerating aging' if v > 0 else 'Slowing aging'}
    for k, v in sorted(contribs.items(), key=lambda x: x[1], reverse=True)
])

colors = [CORAL if v > 0 else TEAL for v in contrib_df['Contribution (PhenoAge years)']]
fig = go.Figure(go.Bar(
    x=contrib_df['Contribution (PhenoAge years)'],
    y=contrib_df['Biomarker'],
    orientation='h',
    marker_color=colors,
    text=[f"{v:+.3f}" for v in contrib_df['Contribution (PhenoAge years)']],
    textposition='outside',
))
fig.add_vline(x=0, line_color='gray', line_width=1)
fig.update_layout(
    title='Biomarker Contributions (positive = accelerating biological aging)',
    xaxis_title='Contribution to PhenoAge Delta (years)',
    plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
    height=380, margin=dict(l=150),
)
st.plotly_chart(fig, width='stretch', key='contrib_bar')

# ── Intervention simulator ────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Simulate Interventions")
st.caption("Adjust any biomarker to its target value and see the real-time effect on PhenoAge. Targets shown are the population median for each biomarker.")

# Show top 3 highest-impact modifiable biomarkers
top_biomarkers = contrib_df[contrib_df['Contribution (PhenoAge years)'] > 0].head(3)
if len(top_biomarkers) > 0:
    names = ', '.join(top_biomarkers['Biomarker'].tolist())
    total_reducible = top_biomarkers['Contribution (PhenoAge years)'].sum()
    st.info(
        f"**Highest-impact targets:** {names}. "
        f"Optimizing these three biomarkers to population median could reduce "
        f"biological age by up to **{total_reducible:.1f} years** for this patient."
    )

# Sliders for simulation
st.markdown("**Adjust biomarker values to simulate interventions:**")
s1, s2, s3 = st.columns(3)

with s1:
    sim_albumin = st.slider("Albumin (g/dL)",
        float(max(2.5, ref_ranges['albumin_gdl'][0])),
        float(min(6.0, ref_ranges['albumin_gdl'][1])),
        float(albumin), step=0.1, key="sl_alb")
    sim_creatinine = st.slider("Creatinine (mg/dL)",
        float(max(0.3, ref_ranges['creatinine_mgdl'][0])),
        float(min(5.0, ref_ranges['creatinine_mgdl'][1])),
        float(creatinine), step=0.1, key="sl_crt")
    sim_glucose = st.slider("Glucose (mg/dL)",
        float(max(50, ref_ranges['glucose_mgdl'][0])),
        float(min(400, ref_ranges['glucose_mgdl'][1])),
        float(glucose), step=1.0, key="sl_glc")

with s2:
    sim_crp = st.slider("CRP (mg/L)",
        float(max(0.01, ref_ranges['crp_mgl'][0])),
        float(min(50.0, ref_ranges['crp_mgl'][1])),
        float(crp), step=0.1, key="sl_crp")
    sim_lymph = st.slider("Lymphocyte %",
        float(max(5.0, ref_ranges['lymph_pct'][0])),
        float(min(80.0, ref_ranges['lymph_pct'][1])),
        float(lymph), step=0.5, key="sl_lym")
    sim_mcv = st.slider("MCV (fL)",
        float(max(70.0, ref_ranges['mcv'][0])),
        float(min(110.0, ref_ranges['mcv'][1])),
        float(mcv), step=0.5, key="sl_mcv")

with s3:
    sim_rdw = st.slider("RDW (%)",
        float(max(10.0, ref_ranges['rdw'][0])),
        float(min(25.0, ref_ranges['rdw'][1])),
        float(rdw), step=0.1, key="sl_rdw")
    sim_alkphos = st.slider("Alkaline Phosphatase (U/L)",
        float(max(20.0, ref_ranges['alkphos'][0])),
        float(min(400.0, ref_ranges['alkphos'][1])),
        float(alkphos), step=1.0, key="sl_alp")
    sim_wbc = st.slider("WBC (×1000/µL)",
        float(max(2.0, ref_ranges['wbc'][0])),
        float(min(20.0, ref_ranges['wbc'][1])),
        float(wbc), step=0.1, key="sl_wbc")

pa_sim   = compute_pa(age, sim_albumin, sim_creatinine, sim_glucose,
                      sim_crp, sim_lymph, sim_mcv, sim_rdw, sim_alkphos, sim_wbc)
delta_sim = pa_sim - age
improvement = delta_current - delta_sim

imp_color = TEAL if improvement > 0 else CORAL
st.markdown(
    f"<div style='background:#F2F4F8;border-left:4px solid {imp_color};"
    f"padding:16px 20px;border-radius:4px;margin:16px 0;'>"
    f"<div style='font-size:14px;color:#1A1A2E;'>"
    f"<strong>Simulated PhenoAge delta:</strong> "
    f"<span style='color:{imp_color};font-size:20px;font-weight:700;'>{delta_sim:+.1f} years</span>"
    f"&nbsp;&nbsp;|&nbsp;&nbsp;"
    f"<strong>Change from baseline:</strong> "
    f"<span style='color:{imp_color};font-size:20px;font-weight:700;'>"
    f"{'−' if improvement > 0 else '+'}{abs(improvement):.1f} years</span>"
    f"</div></div>",
    unsafe_allow_html=True,
)

st.caption(
    "PhenoAge: Levine et al., Aging Cell 2018. Contributions computed as "
    "coeff × (patient_value − NHANES population mean). "
    "This tool is for research and clinical exploration — not a diagnostic instrument."
)
