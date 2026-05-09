"""
Patient Analysis - upload a single lab report (or enter values once) and
explore the same patient across multiple coordinated views.

Tabs:
  1. Biological Age - PhenoAge + delta + 10-yr mortality risk (Levine 2018)
  2. Normative Reference - percentile vs. matched-cohort reference (NHANES)
  3. PhenoAge Intervention - biomarker contribution waterfall + what-if sliders
  4. Metabolic Age - 7-marker organ clock + intervention simulator
  5. Liver Age - 6-marker liver clock + intervention simulator
  6. Kidney Age - 4-marker kidney clock (CKD-EPI 2021 eGFR) + simulator
  7. Reports - INEXION-branded Patient + Physician .docx reports

All tabs read from a single shared input section at the top of the page, so
values entered (or extracted from PDF) flow into every analysis.
No patient data persists beyond the session.
"""
from __future__ import annotations
import io
import json
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from scipy import stats

from src.bioage import compute_phenoage, bootstrap_phenoage
from src.config import NAVY, GOLD, CORAL, TEAL, LIGHT_BG, NHANES_PARQUET, data_exists

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
    # Patient-entered anthropometrics. BMI is derived from height + weight; waist
    # is shown in inches in the UI but converted to cm for the metabolic clock.
    "pa_height_in":   67.0,   # 5'7" matches NHANES adult mean
    "pa_weight_lb":   185.0,  # gives BMI ~28.97, matches NHANES population mean
    "pa_waist_in":    38.85,  # = 98.7 cm NHANES mean / 2.54
    "pa_bmi":         28.9,   # auto-computed each render; default seeds first paint
    "pa_waist":       98.7,   # cm value used by metabolic clock; auto-set from waist_in
    "pa_albumin":     4.3,
    "pa_creatinine":  0.9,
    "pa_glucose":     95.0,
    "pa_crp":         1.5,
    "pa_lymph":       30.0,
    "pa_mcv":         90.0,
    "pa_rdw":         13.0,
    "pa_alkphos":     70.0,
    "pa_wbc":         6.5,
    # Metabolic Age inputs (Tab 4) - NHANES population means as defaults
    "pa_hba1c":       5.7,
    "pa_total_chol":  196.0,
    "pa_hdl":         53.0,
    "pa_sbp":         125.0,
    "pa_dbp":         70.0,
    # Liver Age inputs (Tab 5)
    "pa_tbili":       0.7,
    "pa_total_protein": 7.2,
    "pa_platelet":    251.0,
    "pa_ldh":         134.0,
    # Kidney Age inputs (Tab 6) - eGFR auto-computed
    "pa_bun":         13.7,
    "pa_uric_acid":   5.4,
    "pa_race":        "Non-Hispanic White",
    "pa_extract_msg": "",
    "pa_extract_ok":  False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Track which input keys the user (or PDF extraction) has explicitly set, so
# unset fields can be flagged with a ⚠️ in the UI. A key is considered
# "touched" if (a) PDF extraction populated it, OR (b) the user edited it
# (on_change callback fires), OR (c) its current value differs from the
# seeded default in the DEFAULTS dict.
if "pa_touched_keys" not in st.session_state:
    st.session_state["pa_touched_keys"] = set()


def _mark_touched(key: str) -> None:
    """on_change callback - record that an input was explicitly set."""
    st.session_state["pa_touched_keys"].add(key)


def _is_default(key: str) -> bool:
    """True iff the field still holds its seeded default (and wasn't extracted)."""
    if key in st.session_state["pa_touched_keys"]:
        return False
    return st.session_state.get(key) == DEFAULTS.get(key)


def _mark(label: str, key: str) -> str:
    """Prepend ⚠️ to a label when the input is still showing the default."""
    return f"⚠️ {label}" if _is_default(key) else label

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
        '  "albumin":     <float, g/dL>,\n'
        '  "creatinine":  <float, mg/dL>,\n'
        '  "glucose":     <float, mg/dL fasting>,\n'
        '  "crp":         <float, mg/L; if reported as mg/dL multiply by 10>,\n'
        '  "lymph":       <float, % lymphocyte>,\n'
        '  "mcv":         <float, fL>,\n'
        '  "rdw":         <float, %>,\n'
        '  "alkphos":     <float, U/L alkaline phosphatase>,\n'
        '  "wbc":         <float, x1000/uL>,\n'
        '  "hba1c":       <float, percent (e.g. 5.7)>,\n'
        '  "total_chol":  <float, mg/dL>,\n'
        '  "hdl":         <float, mg/dL>,\n'
        '  "sbp":         <float, mmHg systolic>,\n'
        '  "dbp":         <float, mmHg diastolic>,\n'
        '  "tbili":         <float, mg/dL total bilirubin>,\n'
        '  "total_protein": <float, g/dL total protein>,\n'
        '  "platelet":      <float, x1000/uL platelet count>,\n'
        '  "ldh":           <float, U/L lactate dehydrogenase>,\n'
        '  "bun":           <float, mg/dL blood urea nitrogen>,\n'
        '  "uric_acid":     <float, mg/dL>\n'
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
        "hba1c":      ("pa_hba1c",      3.5,  18.0),
        "total_chol": ("pa_total_chol", 80.0, 400.0),
        "hdl":        ("pa_hdl",        15.0, 150.0),
        "sbp":        ("pa_sbp",        80.0, 220.0),
        "dbp":        ("pa_dbp",        40.0, 130.0),
        "tbili":         ("pa_tbili",         0.1,  10.0),
        "total_protein": ("pa_total_protein", 4.0,  10.0),
        "platelet":      ("pa_platelet",      50.0, 600.0),
        "ldh":           ("pa_ldh",           50.0, 600.0),
        "bun":           ("pa_bun",           3.0,  100.0),
        "uric_acid":     ("pa_uric_acid",     1.5,  15.0),
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
        # Mark every successfully extracted key as "touched" so the ⚠️
        # default-warning emoji disappears from those inputs in the UI.
        for k in found:
            st.session_state["pa_touched_keys"].add(field_map[k][0])
        msg = f"Extracted {len(found)}/{len(field_map)} lab values: {', '.join(found)}."
        if missing:
            msg += f" Not found in report: {', '.join(missing)}. Enter these manually below."
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

# Boxed alert flagging the manual-entry-required fields. These are demographics
# and patient-measured anthropometrics — they are NOT in a lab report, so the
# user has to enter them every time even if they uploaded a complete PDF.
st.info(
    "**Patient-entered values below (Age, Sex, Race / Ethnicity, Height, Weight, "
    "Waist) are not extracted from lab reports — please enter these manually.** "
    "BMI is auto-calculated from height and weight. All lab values further down "
    "auto-populate from a PDF upload (above), or you can edit any value directly. "
    "**Fields marked ⚠️ are still showing NHANES population defaults — edit them "
    "to record the patient's actual values.**"
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

st.markdown("#### Patient-Entered Values")

# Demographics row
dc1, dc2, dc3 = st.columns(3)
with dc1:
    st.number_input(_mark("Age (years)", "pa_age"),
                    min_value=18, max_value=100, step=1, key="pa_age",
                    on_change=_mark_touched, args=("pa_age",))
with dc2:
    st.selectbox(_mark("Sex", "pa_sex"),
                 ["Male", "Female"], key="pa_sex",
                 on_change=_mark_touched, args=("pa_sex",),
                 help="Used for normative reference percentile stratification.")
with dc3:
    st.selectbox(_mark("Race / Ethnicity", "pa_race"),
                 RACE_OPTIONS, key="pa_race",
                 on_change=_mark_touched, args=("pa_race",),
                 help="Used for matched-cohort reference. 'Prefer not to say' "
                      "falls back to age x sex matching.")

# Anthropometrics row - height/weight/waist in US units; BMI is computed
mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    st.number_input(_mark("Height (in)", "pa_height_in"),
                    min_value=48.0, max_value=84.0, step=0.5,
                    key="pa_height_in",
                    on_change=_mark_touched, args=("pa_height_in",),
                    help="Used to calculate BMI from height and weight.")
with mc2:
    st.number_input(_mark("Weight (lb)", "pa_weight_lb"),
                    min_value=70.0, max_value=500.0, step=1.0,
                    key="pa_weight_lb",
                    on_change=_mark_touched, args=("pa_weight_lb",),
                    help="Used to calculate BMI from height and weight.")
with mc3:
    st.number_input(_mark("Waist (in)", "pa_waist_in"),
                    min_value=20.0, max_value=80.0, step=0.5,
                    key="pa_waist_in",
                    on_change=_mark_touched, args=("pa_waist_in",),
                    help="Converted to cm internally for the metabolic clock.")
with mc4:
    # Compute BMI from height + weight using the imperial formula:
    # BMI = (lb / in^2) * 703. Display read-only; the metabolic clock reads
    # st.session_state["pa_bmi"] which we update here every render.
    _h = st.session_state["pa_height_in"]
    _w = st.session_state["pa_weight_lb"]
    bmi_computed = (_w / (_h * _h)) * 703 if _h > 0 else 0.0
    st.session_state["pa_bmi"] = bmi_computed
    st.metric("BMI (computed)", f"{bmi_computed:.1f}")

# Convert waist inches -> cm so downstream code (metabolic clock, intervention
# simulator) keeps reading st.session_state["pa_waist"] in centimeters.
st.session_state["pa_waist"] = st.session_state["pa_waist_in"] * 2.54

st.markdown("#### Lab Values")

# Count and surface how many lab values are still NHANES defaults so the user
# knows at a glance how much manual data entry remains.
_LAB_KEYS = [
    "pa_albumin", "pa_creatinine", "pa_glucose", "pa_bun", "pa_uric_acid",
    "pa_crp", "pa_lymph", "pa_wbc", "pa_mcv", "pa_rdw",
    "pa_hba1c", "pa_total_chol", "pa_hdl", "pa_tbili", "pa_total_protein",
    "pa_alkphos", "pa_platelet", "pa_ldh", "pa_sbp", "pa_dbp",
]
_n_default = sum(1 for k in _LAB_KEYS if _is_default(k))
if _n_default > 0:
    st.caption(
        f"⚠️ **{_n_default} of {len(_LAB_KEYS)} lab values are still NHANES "
        f"population defaults** — they were not found on the uploaded report. "
        "Edit those fields below to enter the patient's actual values. "
        "Marked fields use ⚠️ next to the label."
    )
else:
    st.caption(
        "All lab values entered or extracted. Edit any field directly to override."
    )

# 20 lab values in a single 4-column grid (BMI and waist moved up to
# Patient-Entered Values). Grouped clinically within columns but rendered as
# one continuous section without subheaders or expanders.
lc1, lc2, lc3, lc4 = st.columns(4)
with lc1:
    st.number_input(_mark("Albumin (g/dL)", "pa_albumin"),
                    min_value=2.5,  max_value=6.0,   step=0.1, key="pa_albumin",
                    on_change=_mark_touched, args=("pa_albumin",))
    st.number_input(_mark("Creatinine (mg/dL)", "pa_creatinine"),
                    min_value=0.3,  max_value=5.0,   step=0.1, key="pa_creatinine",
                    on_change=_mark_touched, args=("pa_creatinine",))
    st.number_input(_mark("Glucose (mg/dL)", "pa_glucose"),
                    min_value=50.0, max_value=400.0, step=1.0, key="pa_glucose",
                    on_change=_mark_touched, args=("pa_glucose",))
    st.number_input(_mark("BUN (mg/dL)", "pa_bun"),
                    min_value=3.0,  max_value=100.0, step=0.5, key="pa_bun",
                    on_change=_mark_touched, args=("pa_bun",))
    st.number_input(_mark("Uric acid (mg/dL)", "pa_uric_acid"),
                    min_value=1.5,  max_value=15.0,  step=0.1, key="pa_uric_acid",
                    on_change=_mark_touched, args=("pa_uric_acid",))
with lc2:
    st.number_input(_mark("CRP (mg/L)", "pa_crp"),
                    min_value=0.01, max_value=50.0,  step=0.1, key="pa_crp",
                    on_change=_mark_touched, args=("pa_crp",))
    st.number_input(_mark("Lymphocyte %", "pa_lymph"),
                    min_value=5.0,  max_value=80.0,  step=0.5, key="pa_lymph",
                    on_change=_mark_touched, args=("pa_lymph",))
    st.number_input(_mark("WBC (x1000/uL)", "pa_wbc"),
                    min_value=2.0,  max_value=20.0,  step=0.1, key="pa_wbc",
                    on_change=_mark_touched, args=("pa_wbc",))
    st.number_input(_mark("MCV (fL)", "pa_mcv"),
                    min_value=70.0, max_value=110.0, step=0.5, key="pa_mcv",
                    on_change=_mark_touched, args=("pa_mcv",))
    st.number_input(_mark("RDW (%)", "pa_rdw"),
                    min_value=10.0, max_value=25.0,  step=0.1, key="pa_rdw",
                    on_change=_mark_touched, args=("pa_rdw",))
with lc3:
    st.number_input(_mark("HbA1c (%)", "pa_hba1c"),
                    min_value=3.5,  max_value=18.0,  step=0.1, key="pa_hba1c",
                    on_change=_mark_touched, args=("pa_hba1c",))
    st.number_input(_mark("Total cholesterol (mg/dL)", "pa_total_chol"),
                    min_value=80.0, max_value=400.0, step=1.0, key="pa_total_chol",
                    on_change=_mark_touched, args=("pa_total_chol",))
    st.number_input(_mark("HDL (mg/dL)", "pa_hdl"),
                    min_value=15.0, max_value=150.0, step=1.0, key="pa_hdl",
                    on_change=_mark_touched, args=("pa_hdl",))
    st.number_input(_mark("Total bilirubin (mg/dL)", "pa_tbili"),
                    min_value=0.1,  max_value=10.0,  step=0.1, key="pa_tbili",
                    on_change=_mark_touched, args=("pa_tbili",))
    st.number_input(_mark("Total protein (g/dL)", "pa_total_protein"),
                    min_value=4.0,  max_value=10.0,  step=0.1, key="pa_total_protein",
                    on_change=_mark_touched, args=("pa_total_protein",))
with lc4:
    st.number_input(_mark("Alkaline phosphatase (U/L)", "pa_alkphos"),
                    min_value=20.0, max_value=400.0, step=1.0, key="pa_alkphos",
                    on_change=_mark_touched, args=("pa_alkphos",))
    st.number_input(_mark("Platelet count (x1000/uL)", "pa_platelet"),
                    min_value=50.0, max_value=600.0, step=1.0, key="pa_platelet",
                    on_change=_mark_touched, args=("pa_platelet",))
    st.number_input(_mark("LDH (U/L)", "pa_ldh"),
                    min_value=50.0, max_value=600.0, step=1.0, key="pa_ldh",
                    on_change=_mark_touched, args=("pa_ldh",))
    st.number_input(_mark("Systolic BP (mmHg)", "pa_sbp"),
                    min_value=80.0, max_value=220.0, step=1.0, key="pa_sbp",
                    on_change=_mark_touched, args=("pa_sbp",))
    st.number_input(_mark("Diastolic BP (mmHg)", "pa_dbp"),
                    min_value=40.0, max_value=130.0, step=1.0, key="pa_dbp",
                    on_change=_mark_touched, args=("pa_dbp",))

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
# Metabolic markers
hba1c_pa     = st.session_state["pa_hba1c"]
total_chol_pa = st.session_state["pa_total_chol"]
hdl_pa       = st.session_state["pa_hdl"]
bmi_pa       = st.session_state["pa_bmi"]
waist_pa     = st.session_state["pa_waist"]
sbp_pa       = st.session_state["pa_sbp"]
dbp_pa       = st.session_state["pa_dbp"]
# Liver + Kidney markers
tbili_pa     = st.session_state["pa_tbili"]
tprot_pa     = st.session_state["pa_total_protein"]
plt_pa       = st.session_state["pa_platelet"]
ldh_pa       = st.session_state["pa_ldh"]
bun_pa       = st.session_state["pa_bun"]
ua_pa        = st.session_state["pa_uric_acid"]

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

# Load Phase 4 Metabolic-clock coefficients from organ_clocks_params.json
@st.cache_data(show_spinner=False)
def _load_metabolic_clock():
    from src.config import ORGAN_CLOCKS_PARAMS_PATH, IS_S3
    import json
    try:
        if IS_S3:
            import s3fs
            fs = s3fs.S3FileSystem(anon=False)
            with fs.open(str(ORGAN_CLOCKS_PARAMS_PATH).replace("s3://",""), "r") as f:
                params = json.load(f)
        else:
            with open(ORGAN_CLOCKS_PARAMS_PATH, "r") as f:
                params = json.load(f)
        return params["clocks"]["nhanes_metabolic"]
    except Exception:
        return None

_METAB = _load_metabolic_clock()

# NHANES population means for the metabolic markers (used as the
# "no contribution" baseline in the contribution waterfall).
_METAB_REF_MEANS = {
    "hba1c":             5.72,
    "total_cholesterol": 195.96,
    "hdl":               53.15,
    "bmi":               28.95,
    "waist_cm":          98.72,
    "systolic_mean":     125.01,
    "diastolic_mean":    70.17,
}

# Lab analytical CVs for metabolic-age bootstrap CIs
_METAB_CV = {
    "hba1c": 0.025, "total_cholesterol": 0.030, "hdl": 0.040,
    "bmi": 0.010, "waist_cm": 0.020,
    "systolic_mean": 0.050, "diastolic_mean": 0.050,
}

def compute_metabolic_age(hba1c, total_chol, hdl, bmi, waist, sbp, dbp):
    if _METAB is None or not _METAB.get("fit_ok"):
        return None
    coefs = _METAB["coefficients"]
    val = (
        _METAB["intercept"]
        + coefs["hba1c"]             * hba1c
        + coefs["total_cholesterol"] * total_chol
        + coefs["hdl"]               * hdl
        + coefs["bmi"]               * bmi
        + coefs["waist_cm"]          * waist
        + coefs["systolic_mean"]     * sbp
        + coefs["diastolic_mean"]    * dbp
    )
    return float(val)

def metabolic_contributions(hba1c, total_chol, hdl, bmi, waist, sbp, dbp):
    if _METAB is None or not _METAB.get("fit_ok"):
        return {}
    coefs = _METAB["coefficients"]
    pat = {
        "hba1c": hba1c, "total_cholesterol": total_chol, "hdl": hdl,
        "bmi": bmi, "waist_cm": waist,
        "systolic_mean": sbp, "diastolic_mean": dbp,
    }
    label = {
        "hba1c": "HbA1c", "total_cholesterol": "Total cholesterol", "hdl": "HDL",
        "bmi": "BMI", "waist_cm": "Waist",
        "systolic_mean": "Systolic BP", "diastolic_mean": "Diastolic BP",
    }
    return {label[k]: coefs[k] * (pat[k] - _METAB_REF_MEANS[k])
            for k in pat}

def bootstrap_metabolic(values_dict, n_boot=500, seed=42):
    """Bootstrap the metabolic-age advance using per-marker CV perturbations."""
    rng = np.random.default_rng(seed)
    advances = np.empty(n_boot, dtype=float)
    keys = ["hba1c", "total_cholesterol", "hdl", "bmi", "waist_cm",
            "systolic_mean", "diastolic_mean"]
    sigs = np.array([values_dict[k] * _METAB_CV[k] for k in keys])
    for i in range(n_boot):
        d = rng.normal(0, sigs)
        v = compute_metabolic_age(
            values_dict["hba1c"]             + d[0],
            values_dict["total_cholesterol"] + d[1],
            values_dict["hdl"]               + d[2],
            values_dict["bmi"]               + d[3],
            values_dict["waist_cm"]          + d[4],
            values_dict["systolic_mean"]     + d[5],
            values_dict["diastolic_mean"]    + d[6],
        )
        advances[i] = (v - age) if v is not None else float("nan")
    return {
        "advance_p50": float(np.percentile(advances, 50)),
        "advance_lo":  float(np.percentile(advances, 2.5)),
        "advance_hi":  float(np.percentile(advances, 97.5)),
        "n_boot": n_boot,
    }

@st.cache_data(show_spinner=False)
def _load_organ_clock(name):
    """Load any organ-clock fit dict from organ_clocks_params.json."""
    from src.config import ORGAN_CLOCKS_PARAMS_PATH, IS_S3
    import json
    try:
        if IS_S3:
            import s3fs
            fs = s3fs.S3FileSystem(anon=False)
            with fs.open(str(ORGAN_CLOCKS_PARAMS_PATH).replace("s3://",""), "r") as f:
                params = json.load(f)
        else:
            with open(ORGAN_CLOCKS_PARAMS_PATH, "r") as f:
                params = json.load(f)
        return params["clocks"].get(name)
    except Exception:
        return None

_LIVER  = _load_organ_clock("nhanes_liver")
_KIDNEY = _load_organ_clock("nhanes_kidney")

_LIVER_REF_MEANS = {
    "albumin": 4.21, "alkaline_phosphatase": 70.94,
    "total_bilirubin": 0.67, "total_protein": 7.17,
    "platelet": 251.25, "ldh": 133.62,
}
_LIVER_CV = {
    "albumin": 0.025, "alkaline_phosphatase": 0.040,
    "total_bilirubin": 0.050, "total_protein": 0.020,
    "platelet": 0.040, "ldh": 0.040,
}

_KIDNEY_REF_MEANS = {
    "creatinine": 0.91, "bun": 13.66, "uric_acid": 5.43, "egfr": 93.99,
}
_KIDNEY_CV = {
    "creatinine": 0.030, "bun": 0.050, "uric_acid": 0.030, "egfr": 0.030,
}

def ckd_epi_2021(creatinine, age_yrs, sex_str):
    """Race-free CKD-EPI 2021 eGFR for adults."""
    fem = (sex_str == "Female")
    kappa = 0.7 if fem else 0.9
    alpha = -0.241 if fem else -0.302
    sex_mult = 1.012 if fem else 1.0
    cr_k = creatinine / kappa
    return (
        142.0
        * (min(cr_k, 1.0) ** alpha)
        * (max(cr_k, 1.0) ** -1.200)
        * (0.9938 ** age_yrs)
        * sex_mult
    )

def compute_liver_age(albumin, alkphos, tbili, tprot, plt, ldh):
    if _LIVER is None or not _LIVER.get("fit_ok"):
        return None
    c = _LIVER["coefficients"]
    return float(
        _LIVER["intercept"]
        + c["albumin"]              * albumin
        + c["alkaline_phosphatase"] * alkphos
        + c["total_bilirubin"]      * tbili
        + c["total_protein"]        * tprot
        + c["platelet"]             * plt
        + c["ldh"]                  * ldh
    )

def liver_contributions(albumin, alkphos, tbili, tprot, plt, ldh):
    if _LIVER is None or not _LIVER.get("fit_ok"):
        return {}
    c = _LIVER["coefficients"]
    pat = {"albumin": albumin, "alkaline_phosphatase": alkphos,
           "total_bilirubin": tbili, "total_protein": tprot,
           "platelet": plt, "ldh": ldh}
    label = {"albumin": "Albumin",
              "alkaline_phosphatase": "Alkaline phosphatase",
              "total_bilirubin": "Total bilirubin",
              "total_protein": "Total protein",
              "platelet": "Platelets", "ldh": "LDH"}
    return {label[k]: c[k] * (pat[k] - _LIVER_REF_MEANS[k]) for k in pat}

def bootstrap_liver(values, n_boot=400, seed=42):
    rng = np.random.default_rng(seed)
    advances = np.empty(n_boot, dtype=float)
    keys = ["albumin", "alkaline_phosphatase", "total_bilirubin",
            "total_protein", "platelet", "ldh"]
    sigs = np.array([values[k] * _LIVER_CV[k] for k in keys])
    for i in range(n_boot):
        d = rng.normal(0, sigs)
        v = compute_liver_age(*[values[k] + d[j] for j, k in enumerate(keys)])
        advances[i] = (v - age) if v is not None else float("nan")
    return {"advance_p50": float(np.percentile(advances, 50)),
            "advance_lo": float(np.percentile(advances, 2.5)),
            "advance_hi": float(np.percentile(advances, 97.5)),
            "n_boot": n_boot}

def compute_kidney_age(creatinine, bun, ua, egfr):
    if _KIDNEY is None or not _KIDNEY.get("fit_ok"):
        return None
    c = _KIDNEY["coefficients"]
    return float(
        _KIDNEY["intercept"]
        + c["creatinine"] * creatinine
        + c["bun"]        * bun
        + c["uric_acid"]  * ua
        + c["egfr"]       * egfr
    )

def kidney_contributions(creatinine, bun, ua, egfr):
    if _KIDNEY is None or not _KIDNEY.get("fit_ok"):
        return {}
    c = _KIDNEY["coefficients"]
    pat = {"creatinine": creatinine, "bun": bun, "uric_acid": ua, "egfr": egfr}
    label = {"creatinine": "Creatinine", "bun": "BUN",
              "uric_acid": "Uric acid", "egfr": "eGFR (CKD-EPI)"}
    return {label[k]: c[k] * (pat[k] - _KIDNEY_REF_MEANS[k]) for k in pat}

def bootstrap_kidney(values, n_boot=400, seed=42):
    rng = np.random.default_rng(seed)
    advances = np.empty(n_boot, dtype=float)
    keys = ["creatinine", "bun", "uric_acid", "egfr"]
    sigs = np.array([values[k] * _KIDNEY_CV[k] for k in keys])
    for i in range(n_boot):
        d = rng.normal(0, sigs)
        v = compute_kidney_age(*[values[k] + d[j] for j, k in enumerate(keys)])
        advances[i] = (v - age) if v is not None else float("nan")
    return {"advance_p50": float(np.percentile(advances, 50)),
            "advance_lo": float(np.percentile(advances, 2.5)),
            "advance_hi": float(np.percentile(advances, 97.5)),
            "n_boot": n_boot}

tabs = st.tabs(["Biological Age (PhenoAge)", "Normative Reference",
                "PhenoAge Intervention", "Metabolic Age",
                "Liver Age", "Kidney Age", "Reports"])

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

        fig_ci = go.Figure()
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

# =============================================================================
# TAB 4 - METABOLIC AGE
# =============================================================================
with tabs[3]:
    if _METAB is None or not _METAB.get("fit_ok"):
        st.warning("Metabolic clock coefficients not loaded. "
                    "Check organ_clocks_params.json in S3.")
    else:
        m_age = compute_metabolic_age(hba1c_pa, total_chol_pa, hdl_pa,
                                        bmi_pa, waist_pa, sbp_pa, dbp_pa)
        m_advance = m_age - age
        m_color = TEAL if m_advance <= 0 else CORAL
        m_label = "biologically younger" if m_advance <= 0 else "biologically older"

        # Bootstrap CI on metabolic advance
        m_ci = bootstrap_metabolic({
            "hba1c": hba1c_pa, "total_cholesterol": total_chol_pa, "hdl": hdl_pa,
            "bmi": bmi_pa, "waist_cm": waist_pa,
            "systolic_mean": sbp_pa, "diastolic_mean": dbp_pa,
        }, n_boot=500)

        st.markdown(
            f"""
            <div style='background:{NAVY}; color:white; padding:28px;
                        border-radius:10px; text-align:center; margin-top:8px;'>
                <div style='color:{GOLD}; font-size:12px; letter-spacing:2px;
                            text-transform:uppercase;'>Metabolic Age (NHANES-trained)</div>
                <div style='font-size:56px; font-weight:800; margin-top:6px;'>
                    {m_age:.1f} <span style='color:{GOLD}; font-size:28px;'>years</span>
                </div>
                <div style='font-size:18px; color:{m_color}; margin-top:8px; font-weight:600;'>
                    {m_advance:+.1f} years - {m_label} than chronological age
                </div>
                <div style='font-size:14px; color:#C9CBD4; margin-top:4px;'>
                    95% CI on advance: [{m_ci['advance_lo']:+.1f}, {m_ci['advance_hi']:+.1f}] years
                    &nbsp;-&nbsp; bootstrap n={m_ci['n_boot']}
                </div>
                <div style='font-size:13px; color:#C9CBD4; margin-top:14px;'>
                    Phase 4 NHANES-trained metabolic clock. R^2={_METAB['r2']:.3f},
                    age-adjusted Cox HR=1.027/yr advance, C-index=0.835.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### Marker contributions to metabolic-age advance")
        st.caption(
            "Each bar = coefficient * (patient value - NHANES population mean) "
            "in years. Positive (coral) = pulling metabolic age UP; negative (teal) "
            "= pulling DOWN. Some signs (HDL, BMI, DBP) reflect within-NHANES "
            "age-correlation rather than clinical desirability - see disclaimer below."
        )
        contribs = metabolic_contributions(hba1c_pa, total_chol_pa, hdl_pa,
                                            bmi_pa, waist_pa, sbp_pa, dbp_pa)
        cdf = pd.DataFrame([{"Marker": k, "Contribution (yrs)": v}
                             for k, v in sorted(contribs.items(),
                                                 key=lambda x: x[1], reverse=True)])
        colors = [CORAL if v > 0 else TEAL for v in cdf["Contribution (yrs)"]]
        fig = go.Figure(go.Bar(
            x=cdf["Contribution (yrs)"], y=cdf["Marker"],
            orientation='h', marker_color=colors,
            text=[f"{v:+.2f}" for v in cdf["Contribution (yrs)"]],
            textposition='outside',
        ))
        fig.add_vline(x=0, line_color='gray', line_width=1)
        fig.update_layout(
            xaxis_title='Contribution to metabolic-age advance (years)',
            plot_bgcolor='white', paper_bgcolor='white',
            font_color='#1A1A2E', height=320, margin=dict(l=140, t=10, b=40, r=20),
        )
        st.plotly_chart(fig, use_container_width=True, key='pa_metab_contrib')

        st.markdown("##### Simulate intervention")
        st.caption(
            "Sliders default to current values. Move them to see how the metabolic "
            "age advance would shift if the patient hit different targets."
        )
        msig = (hba1c_pa, total_chol_pa, hdl_pa, bmi_pa, waist_pa, sbp_pa, dbp_pa)
        if st.session_state.get("pa_metab_baseline_sig") != msig:
            st.session_state["pa_metab_baseline_sig"] = msig
            for k, v in zip(("ms_hba1c","ms_chol","ms_hdl","ms_bmi","ms_waist","ms_sbp","ms_dbp"),
                             msig):
                st.session_state[k] = float(v)

        ms1, ms2, ms3 = st.columns(3)
        with ms1:
            sim_hba1c = st.slider("HbA1c (%)", 4.0, 14.0, step=0.1, key="ms_hba1c")
            sim_chol  = st.slider("Total cholesterol (mg/dL)", 100.0, 350.0, step=1.0, key="ms_chol")
            sim_hdl   = st.slider("HDL (mg/dL)", 20.0, 120.0, step=1.0, key="ms_hdl")
        with ms2:
            sim_bmi   = st.slider("BMI (kg/m^2)", 18.0, 50.0, step=0.1, key="ms_bmi")
            sim_waist = st.slider("Waist (cm)", 60.0, 160.0, step=0.5, key="ms_waist")
        with ms3:
            sim_sbp = st.slider("Systolic BP (mmHg)", 90.0, 200.0, step=1.0, key="ms_sbp")
            sim_dbp = st.slider("Diastolic BP (mmHg)", 50.0, 120.0, step=1.0, key="ms_dbp")

        m_sim_age = compute_metabolic_age(sim_hba1c, sim_chol, sim_hdl,
                                            sim_bmi, sim_waist, sim_sbp, sim_dbp)
        m_sim_advance = m_sim_age - age
        m_change = m_advance - m_sim_advance
        ms_color = TEAL if m_change > 0 else CORAL
        sign_m = "-" if m_change > 0 else "+"

        m_sim_ci = bootstrap_metabolic({
            "hba1c": sim_hba1c, "total_cholesterol": sim_chol, "hdl": sim_hdl,
            "bmi": sim_bmi, "waist_cm": sim_waist,
            "systolic_mean": sim_sbp, "diastolic_mean": sim_dbp,
        }, n_boot=300)

        st.markdown(
            f"<div style='background:#F2F4F8;border-left:4px solid {ms_color};"
            f"padding:16px 20px;border-radius:4px;margin:16px 0;'>"
            f"<div style='font-size:14px;color:#1A1A2E;'>"
            f"<strong>Simulated metabolic age advance:</strong> "
            f"<span style='color:{ms_color};font-size:20px;font-weight:700;'>{m_sim_advance:+.1f} years</span>"
            f"&nbsp;<span style='color:#6B7280;font-size:13px;'>"
            f"[CI {m_sim_ci['advance_lo']:+.1f}, {m_sim_ci['advance_hi']:+.1f}]</span>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<strong>Change from baseline:</strong> "
            f"<span style='color:{ms_color};font-size:20px;font-weight:700;'>{sign_m}{abs(m_change):.1f} years</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        m_fig_ci = go.Figure()
        m_fig_ci.add_trace(go.Scatter(
            x=[m_ci['advance_lo'], m_ci['advance_hi']], y=[1, 1],
            mode='lines', line=dict(color=NAVY, width=10),
            name='Baseline 95% CI'))
        m_fig_ci.add_trace(go.Scatter(
            x=[m_advance], y=[1], mode='markers',
            marker=dict(color=GOLD, size=18, line=dict(color=NAVY, width=2)),
            showlegend=False))
        m_fig_ci.add_trace(go.Scatter(
            x=[m_sim_ci['advance_lo'], m_sim_ci['advance_hi']], y=[0, 0],
            mode='lines', line=dict(color=ms_color, width=10),
            name='Simulated 95% CI'))
        m_fig_ci.add_trace(go.Scatter(
            x=[m_sim_advance], y=[0], mode='markers',
            marker=dict(color=GOLD, size=18, line=dict(color=ms_color, width=2)),
            showlegend=False))
        m_fig_ci.add_vline(x=0, line_dash='dash', line_color='gray',
                            annotation_text='No advance', annotation_position='top')
        m_no_overlap = (m_sim_ci['advance_hi'] < m_ci['advance_lo']) or (m_sim_ci['advance_lo'] > m_ci['advance_hi'])
        m_verdict = ("Simulated CI does NOT overlap baseline CI - change exceeds lab noise."
                      if m_no_overlap else
                      "Simulated CI overlaps baseline CI - change is within lab noise.")
        m_pad = max(2.0, abs(m_advance) * 0.5, abs(m_sim_advance) * 0.5)
        m_x_lo = min(m_ci['advance_lo'], m_sim_ci['advance_lo']) - 1
        m_x_hi = max(m_ci['advance_hi'], m_sim_ci['advance_hi']) + 1
        m_fig_ci.update_layout(
            height=180, plot_bgcolor='white', paper_bgcolor='white',
            font_color='#1A1A2E',
            xaxis=dict(title='Metabolic-age advance (years)',
                        range=[min(m_x_lo, -m_pad), max(m_x_hi, m_pad)], zeroline=False),
            yaxis=dict(visible=False, range=[-0.5, 1.5],
                        tickvals=[0, 1], ticktext=['Simulated', 'Baseline']),
            yaxis_showticklabels=True,
            margin=dict(t=10, b=40, l=80, r=20),
            legend=dict(orientation='h', y=-0.25),
        )
        st.plotly_chart(m_fig_ci, use_container_width=True, key='pa_metab_dualci')
        st.caption(m_verdict)

        st.caption(
            "**Methodology note.** This metabolic clock is a within-NHANES "
            "regression of chronological age on the 7 markers. Some coefficients "
            "(HDL +, BMI -, DBP -) are counter-intuitive because of multivariate "
            "age-confounding (e.g., DBP falls with vascular stiffening at older "
            "ages, BMI peaks middle-age and falls). The clock validates against "
            "mortality (HR=1.027/yr advance, C=0.835), but DO NOT use the simulator "
            "as clinical advice. Lowering HDL or raising BMI to 'improve' metabolic "
            "age is incorrect clinically; the model captures statistical age-pattern "
            "matching, not health-outcome optimization. Use it for understanding "
            "how a patient's metabolic profile compares to age peers."
        )


# =============================================================================
# TAB 5 - LIVER AGE
# =============================================================================
with tabs[4]:
    if _LIVER is None or not _LIVER.get("fit_ok"):
        st.warning("Liver clock coefficients not loaded.")
    else:
        l_age = compute_liver_age(albumin, alkphos, tbili_pa, tprot_pa, plt_pa, ldh_pa)
        l_advance = l_age - age
        l_color = TEAL if l_advance <= 0 else CORAL
        l_label = "biologically younger" if l_advance <= 0 else "biologically older"

        l_ci = bootstrap_liver({
            "albumin": albumin, "alkaline_phosphatase": alkphos,
            "total_bilirubin": tbili_pa, "total_protein": tprot_pa,
            "platelet": plt_pa, "ldh": ldh_pa,
        }, n_boot=400)

        st.markdown(
            f"""
            <div style='background:{NAVY}; color:white; padding:28px;
                        border-radius:10px; text-align:center; margin-top:8px;'>
                <div style='color:{GOLD}; font-size:12px; letter-spacing:2px;
                            text-transform:uppercase;'>Liver Age (NHANES-trained, synthetic-function panel)</div>
                <div style='font-size:56px; font-weight:800; margin-top:6px;'>
                    {l_age:.1f} <span style='color:{GOLD}; font-size:28px;'>years</span>
                </div>
                <div style='font-size:18px; color:{l_color}; margin-top:8px; font-weight:600;'>
                    {l_advance:+.1f} years - {l_label} than chronological age
                </div>
                <div style='font-size:14px; color:#C9CBD4; margin-top:4px;'>
                    95% CI on advance: [{l_ci['advance_lo']:+.1f}, {l_ci['advance_hi']:+.1f}] years &nbsp;-&nbsp; bootstrap n={l_ci['n_boot']}
                </div>
                <div style='font-size:13px; color:#C9CBD4; margin-top:14px;'>
                    Phase 4 NHANES-trained liver clock. R^2={_LIVER['r2']:.3f}, age-adjusted Cox HR=1.081/yr advance, C-index=0.849.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### Marker contributions to liver-age advance")
        l_contribs = liver_contributions(albumin, alkphos, tbili_pa, tprot_pa, plt_pa, ldh_pa)
        ldf = pd.DataFrame([{"Marker": k, "Contribution (yrs)": v}
                             for k, v in sorted(l_contribs.items(), key=lambda x: x[1], reverse=True)])
        l_colors = [CORAL if v > 0 else TEAL for v in ldf["Contribution (yrs)"]]
        l_fig = go.Figure(go.Bar(
            x=ldf["Contribution (yrs)"], y=ldf["Marker"], orientation='h',
            marker_color=l_colors,
            text=[f"{v:+.2f}" for v in ldf["Contribution (yrs)"]], textposition='outside',
        ))
        l_fig.add_vline(x=0, line_color='gray', line_width=1)
        l_fig.update_layout(xaxis_title='Contribution to liver-age advance (years)',
                            plot_bgcolor='white', paper_bgcolor='white',
                            font_color='#1A1A2E', height=320,
                            margin=dict(l=160, t=10, b=40, r=20))
        st.plotly_chart(l_fig, use_container_width=True, key='pa_liver_contrib')

        st.markdown("##### Simulate intervention")
        lsig = (albumin, alkphos, tbili_pa, tprot_pa, plt_pa, ldh_pa)
        if st.session_state.get("pa_liver_baseline_sig") != lsig:
            st.session_state["pa_liver_baseline_sig"] = lsig
            for k, v in zip(("ls_alb","ls_alp","ls_tb","ls_tp","ls_plt","ls_ldh"), lsig):
                st.session_state[k] = float(v)
        l1, l2, l3 = st.columns(3)
        with l1:
            sim_alb = st.slider("Albumin (g/dL)",            2.5, 6.0,  step=0.1, key="ls_alb")
            sim_alp = st.slider("Alkaline phosphatase (U/L)", 20.0, 400.0, step=1.0, key="ls_alp")
        with l2:
            sim_tb = st.slider("Total bilirubin (mg/dL)",    0.1, 5.0,  step=0.05, key="ls_tb")
            sim_tp = st.slider("Total protein (g/dL)",       4.0, 10.0, step=0.1, key="ls_tp")
        with l3:
            sim_plt = st.slider("Platelets (x1000/uL)",      50.0, 600.0, step=1.0, key="ls_plt")
            sim_ldh = st.slider("LDH (U/L)",                 50.0, 400.0, step=1.0, key="ls_ldh")

        l_sim_age = compute_liver_age(sim_alb, sim_alp, sim_tb, sim_tp, sim_plt, sim_ldh)
        l_sim_advance = l_sim_age - age
        l_change = l_advance - l_sim_advance
        ls_color = TEAL if l_change > 0 else CORAL
        sign_l = "-" if l_change > 0 else "+"
        l_sim_ci = bootstrap_liver({
            "albumin": sim_alb, "alkaline_phosphatase": sim_alp,
            "total_bilirubin": sim_tb, "total_protein": sim_tp,
            "platelet": sim_plt, "ldh": sim_ldh,
        }, n_boot=300)

        st.markdown(
            f"<div style='background:#F2F4F8;border-left:4px solid {ls_color};"
            f"padding:16px 20px;border-radius:4px;margin:16px 0;'>"
            f"<div style='font-size:14px;color:#1A1A2E;'>"
            f"<strong>Simulated liver age advance:</strong> "
            f"<span style='color:{ls_color};font-size:20px;font-weight:700;'>{l_sim_advance:+.1f} years</span>"
            f"&nbsp;<span style='color:#6B7280;font-size:13px;'>"
            f"[CI {l_sim_ci['advance_lo']:+.1f}, {l_sim_ci['advance_hi']:+.1f}]</span>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<strong>Change from baseline:</strong> "
            f"<span style='color:{ls_color};font-size:20px;font-weight:700;'>{sign_l}{abs(l_change):.1f} years</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        st.caption(
            "**Methodology note.** Liver Age R^2 is only 0.06 - this clock is a "
            "weak fit, because the NHANES parquet does not yet include ALT / AST / "
            "GGT (the canonical hepatocellular-injury enzymes). What's here is "
            "albumin + alkaline phosphatase + total bilirubin + total protein + "
            "platelets + LDH - a synthetic-function and clearance panel rather "
            "than an injury panel. The clock still validates against mortality "
            "(HR=1.081/yr advance, C=0.849), but treat individual patient "
            "scores as exploratory until the injury enzymes are ingested into "
            "the NHANES pipeline."
        )


# =============================================================================
# TAB 6 - KIDNEY AGE
# =============================================================================
with tabs[5]:
    if _KIDNEY is None or not _KIDNEY.get("fit_ok"):
        st.warning("Kidney clock coefficients not loaded.")
    else:
        egfr_pa = ckd_epi_2021(creatinine, age, sex)
        k_age = compute_kidney_age(creatinine, bun_pa, ua_pa, egfr_pa)
        k_advance = k_age - age
        k_color = TEAL if k_advance <= 0 else CORAL
        k_label = "biologically younger" if k_advance <= 0 else "biologically older"

        k_ci = bootstrap_kidney({
            "creatinine": creatinine, "bun": bun_pa,
            "uric_acid": ua_pa, "egfr": egfr_pa,
        }, n_boot=400)

        st.markdown(
            f"""
            <div style='background:{NAVY}; color:white; padding:28px;
                        border-radius:10px; text-align:center; margin-top:8px;'>
                <div style='color:{GOLD}; font-size:12px; letter-spacing:2px;
                            text-transform:uppercase;'>Kidney Age (NHANES-trained, CKD-EPI 2021 eGFR)</div>
                <div style='font-size:56px; font-weight:800; margin-top:6px;'>
                    {k_age:.1f} <span style='color:{GOLD}; font-size:28px;'>years</span>
                </div>
                <div style='font-size:18px; color:{k_color}; margin-top:8px; font-weight:600;'>
                    {k_advance:+.1f} years - {k_label} than chronological age
                </div>
                <div style='font-size:14px; color:#C9CBD4; margin-top:4px;'>
                    95% CI on advance: [{k_ci['advance_lo']:+.1f}, {k_ci['advance_hi']:+.1f}] years &nbsp;-&nbsp; bootstrap n={k_ci['n_boot']}
                </div>
                <div style='font-size:13px; color:#C9CBD4; margin-top:14px;'>
                    Phase 4 NHANES-trained kidney clock. R^2={_KIDNEY['r2']:.3f}, age-adjusted Cox HR=1.018/yr advance, C-index=0.842.
                    Computed eGFR (CKD-EPI 2021): {egfr_pa:.1f} mL/min/1.73m^2.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### Marker contributions to kidney-age advance")
        k_contribs = kidney_contributions(creatinine, bun_pa, ua_pa, egfr_pa)
        kdf = pd.DataFrame([{"Marker": k, "Contribution (yrs)": v}
                             for k, v in sorted(k_contribs.items(), key=lambda x: x[1], reverse=True)])
        k_colors = [CORAL if v > 0 else TEAL for v in kdf["Contribution (yrs)"]]
        k_fig = go.Figure(go.Bar(
            x=kdf["Contribution (yrs)"], y=kdf["Marker"], orientation='h',
            marker_color=k_colors,
            text=[f"{v:+.2f}" for v in kdf["Contribution (yrs)"]], textposition='outside',
        ))
        k_fig.add_vline(x=0, line_color='gray', line_width=1)
        k_fig.update_layout(xaxis_title='Contribution to kidney-age advance (years)',
                            plot_bgcolor='white', paper_bgcolor='white',
                            font_color='#1A1A2E', height=300,
                            margin=dict(l=160, t=10, b=40, r=20))
        st.plotly_chart(k_fig, use_container_width=True, key='pa_kidney_contrib')

        st.markdown("##### Simulate intervention")
        st.caption(
            "Adjust creatinine, BUN, or uric acid. eGFR is auto-recomputed via "
            "CKD-EPI 2021 from the simulated creatinine + the patient's age and sex."
        )
        ksig = (creatinine, bun_pa, ua_pa)
        if st.session_state.get("pa_kidney_baseline_sig") != ksig:
            st.session_state["pa_kidney_baseline_sig"] = ksig
            for k, v in zip(("ks_cre","ks_bun","ks_ua"), ksig):
                st.session_state[k] = float(v)
        k1, k2, k3 = st.columns(3)
        with k1:
            sim_cre = st.slider("Creatinine (mg/dL)", 0.4, 5.0, step=0.05, key="ks_cre")
        with k2:
            sim_bun = st.slider("BUN (mg/dL)",         3.0, 80.0, step=0.5, key="ks_bun")
        with k3:
            sim_ua  = st.slider("Uric acid (mg/dL)",   1.5, 14.0, step=0.1, key="ks_ua")

        sim_egfr = ckd_epi_2021(sim_cre, age, sex)
        k_sim_age = compute_kidney_age(sim_cre, sim_bun, sim_ua, sim_egfr)
        k_sim_advance = k_sim_age - age
        k_change = k_advance - k_sim_advance
        ks_color = TEAL if k_change > 0 else CORAL
        sign_k = "-" if k_change > 0 else "+"
        k_sim_ci = bootstrap_kidney({
            "creatinine": sim_cre, "bun": sim_bun,
            "uric_acid": sim_ua, "egfr": sim_egfr,
        }, n_boot=300)

        st.markdown(
            f"<div style='background:#F2F4F8;border-left:4px solid {ks_color};"
            f"padding:16px 20px;border-radius:4px;margin:16px 0;'>"
            f"<div style='font-size:14px;color:#1A1A2E;'>"
            f"<strong>Simulated kidney age advance:</strong> "
            f"<span style='color:{ks_color};font-size:20px;font-weight:700;'>{k_sim_advance:+.1f} years</span>"
            f"&nbsp;<span style='color:#6B7280;font-size:13px;'>"
            f"[CI {k_sim_ci['advance_lo']:+.1f}, {k_sim_ci['advance_hi']:+.1f}]</span>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<strong>Change from baseline:</strong> "
            f"<span style='color:{ks_color};font-size:20px;font-weight:700;'>{sign_k}{abs(k_change):.1f} years</span>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<span style='color:#6B7280;font-size:13px;'>simulated eGFR: {sim_egfr:.1f}</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

        st.caption(
            "**Methodology note.** Kidney Age R^2 = 0.40 - the strongest within-cohort "
            "fit of the four organ clocks, because creatinine and eGFR track age tightly. "
            "Note that creatinine and eGFR are deterministic functions of each other "
            "(plus age + sex), so the marginal coefficients on each look counter-intuitive "
            "in isolation. The contribution waterfall reflects multivariate fit, not "
            "individual marker effects. Cox HR=1.018/yr advance, C=0.842."
        )


# ---------------------------------------------------------------------------
# TAB 7 - REPORTS
# Comprehensive INEXION-branded .docx outputs for patient + clinician audiences.
# Pulls everything from session state + the computed clocks above and hands it
# off to src.reports for narrative generation (Claude Haiku) and docx assembly.
# ---------------------------------------------------------------------------
with tabs[6]:
    st.markdown(
        f"<div style='background:{NAVY};color:white;padding:22px 28px;"
        f"border-radius:8px;margin-bottom:18px;'>"
        f"<div style='color:{GOLD};font-size:11px;letter-spacing:2px;"
        f"text-transform:uppercase;font-weight:600;'>INEXION Longevity Registry</div>"
        f"<div style='font-size:22px;font-weight:700;margin-top:4px;'>"
        f"Generate Patient & Physician Reports</div>"
        f"<div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>"
        f"Two INEXION-branded Word documents that wrap up everything from "
        f"the analyses above into a shareable, written deliverable.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Compile the data payload that both report builders consume. All values
    # come from session state (already validated by the input section above)
    # plus the clocks computed earlier in this page.
    _LOGO_PATH_RPT = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "assets", "inexion_logo.png"
    )

    rpt_patient = {
        "age":       int(st.session_state["pa_age"]),
        "sex":       st.session_state["pa_sex"],
        "race":      st.session_state.get("pa_race", ""),
        "height_in": float(st.session_state["pa_height_in"]),
        "weight_lb": float(st.session_state["pa_weight_lb"]),
        "bmi":       float(st.session_state["pa_bmi"]),
        "waist_in":  float(st.session_state["pa_waist_in"]),
    }
    rpt_labs = {
        "albumin": albumin, "creatinine": creatinine, "glucose": glucose,
        "bun": bun_pa, "uric_acid": ua_pa,
        "crp": crp, "lymph": lymph, "wbc": wbc, "mcv": mcv, "rdw": rdw,
        "hba1c": hba1c_pa, "total_chol": total_chol_pa, "hdl": hdl_pa,
        "tbili": tbili_pa, "total_protein": tprot_pa,
        "alkphos": alkphos, "platelet": plt_pa, "ldh": ldh_pa,
        "sbp": sbp_pa, "dbp": dbp_pa,
    }

    # Compute organ clocks; tolerate missing models by leaving values as None.
    _metabolic_age = compute_metabolic_age(
        hba1c_pa, total_chol_pa, hdl_pa, bmi_pa, waist_pa, sbp_pa, dbp_pa)
    _liver_age = compute_liver_age(
        albumin, alkphos, tbili_pa, tprot_pa, plt_pa, ldh_pa)
    _egfr_pa = ckd_epi_2021(creatinine, age, sex)
    _kidney_age = compute_kidney_age(creatinine, bun_pa, ua_pa, _egfr_pa)

    rpt_organ_ages = {
        "metabolic_age":   _metabolic_age,
        "metabolic_delta": (_metabolic_age - age) if _metabolic_age is not None else None,
        "liver_age":       _liver_age,
        "liver_delta":     (_liver_age - age) if _liver_age is not None else None,
        "kidney_age":      _kidney_age,
        "kidney_delta":    (_kidney_age - age) if _kidney_age is not None else None,
    }

    # PhenoAge contributions - inline reference means (NHANES adult population)
    # so the Reports tab works even without the parquet loaded in this session.
    _PHENOAGE_RPT_REF = {
        "albumin_si": 43.0, "creatinine_si": 79.56, "glucose_si": 5.27,
        "ln_crp": 0.405, "lymph_pct": 30.0, "mcv": 90.0,
        "rdw": 13.0, "alkphos": 70.0, "wbc": 6.5,
    }
    _PHENOAGE_RPT_COEFFS = {
        "albumin_si": -0.03359355, "creatinine_si": 0.009506491,
        "glucose_si": 0.1953192, "ln_crp": 0.09536762,
        "lymph_pct": -0.01199984, "mcv": 0.02676401,
        "rdw": 0.3306156, "alkphos": 0.001868778, "wbc": 0.05542406,
    }
    _PHENOAGE_RPT_LABEL = {
        "albumin_si": "Albumin", "creatinine_si": "Creatinine",
        "glucose_si": "Glucose", "ln_crp": "CRP",
        "lymph_pct": "Lymphocyte %", "mcv": "MCV", "rdw": "RDW",
        "alkphos": "Alkaline phosphatase", "wbc": "WBC",
    }
    _pat_pa_vals = {
        "albumin_si":    albumin * 10.0,
        "creatinine_si": creatinine * 88.4,
        "glucose_si":    glucose / 18.02,
        "ln_crp":        math.log(max(crp, 0.01)),
        "lymph_pct":     lymph,
        "mcv":           mcv,
        "rdw":           rdw,
        "alkphos":       alkphos,
        "wbc":           wbc,
    }
    _pheno_contribs = {
        _PHENOAGE_RPT_LABEL[k]:
            _PHENOAGE_RPT_COEFFS[k] * (_pat_pa_vals[k] - _PHENOAGE_RPT_REF[k])
        for k in _PHENOAGE_RPT_COEFFS
    }
    _metab_contribs  = metabolic_contributions(
        hba1c_pa, total_chol_pa, hdl_pa, bmi_pa, waist_pa, sbp_pa, dbp_pa) or {}
    _liver_contribs  = liver_contributions(
        albumin, alkphos, tbili_pa, tprot_pa, plt_pa, ldh_pa) or {}
    _kidney_contribs = kidney_contributions(
        creatinine, bun_pa, ua_pa, _egfr_pa) or {}

    rpt_contributions = {
        "PhenoAge":      _pheno_contribs,
        "Metabolic age": _metab_contribs,
        "Liver age":     _liver_contribs,
        "Kidney age":    _kidney_contribs,
    }
    rpt_phenoage = {
        "phenoage":      phenoage,
        "delta":         delta,
        "mortality_10y": mortality,
    }

    # Two side-by-side report cards
    rcol_a, rcol_b = st.columns(2)
    with rcol_a:
        st.markdown(
            f"""
            <div style='background:{LIGHT_BG};border-left:5px solid {NAVY};
                        padding:20px;border-radius:6px;height:260px;'>
            <div style='color:{NAVY};font-weight:700;font-size:18px;
                        margin-bottom:8px;'>Patient Report</div>
            <div style='color:#1A1A2E;font-size:13px;line-height:1.55;'>
                A comprehensive INEXION-branded guidebook in patient-friendly
                language. Explains every lab value plainly, walks through
                biological / metabolic / liver / kidney age, the population
                percentile, and prioritized lifestyle recommendations the
                patient can act on this month. Written at an ~8th-grade
                reading level.
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        if st.button("Generate Patient Report",
                      key="gen_pt_rpt", type="primary", use_container_width=True):
            try:
                from src.reports import build_patient_report
                with st.spinner("Generating Patient Report..."):
                    pt_bytes = build_patient_report(
                        patient=rpt_patient,
                        labs=rpt_labs,
                        phenoage=rpt_phenoage,
                        organ_ages=rpt_organ_ages,
                        contributions=rpt_contributions,
                        percentile=None,
                        logo_path=_LOGO_PATH_RPT,
                    )
                st.session_state["pa_patient_report_bytes"] = pt_bytes
                st.success("Patient Report ready - download below.")
            except Exception as e:
                st.error(f"Could not generate Patient Report: {e}")

        if st.session_state.get("pa_patient_report_bytes"):
            st.download_button(
                "⬇ Download Patient Report (.pdf)",
                data=st.session_state["pa_patient_report_bytes"],
                file_name=(
                    f"INEXION_Patient_Report_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                ),
                mime="application/pdf",
                key="dl_pt_rpt",
                use_container_width=True,
            )

    with rcol_b:
        st.markdown(
            f"""
            <div style='background:{LIGHT_BG};border-left:5px solid {GOLD};
                        padding:20px;border-radius:6px;height:260px;'>
            <div style='color:{NAVY};font-weight:700;font-size:18px;
                        margin-bottom:8px;'>Physician Report</div>
            <div style='color:#1A1A2E;font-size:13px;line-height:1.55;'>
                A clinical decision-support document at clinician health
                literacy. Surfaces biomarker contribution analysis - which
                markers most accelerate or decelerate this patient's age
                across all four clocks - and ranks intervention targets by
                predicted &Delta;-age impact with concrete approach options.
                Includes a full lab reference table.
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        if st.button("Generate Physician Report",
                      key="gen_phys_rpt", use_container_width=True):
            try:
                from src.reports import build_physician_report
                with st.spinner("Generating Physician Report..."):
                    phys_bytes = build_physician_report(
                        patient=rpt_patient,
                        labs=rpt_labs,
                        phenoage=rpt_phenoage,
                        organ_ages=rpt_organ_ages,
                        contributions=rpt_contributions,
                        percentile=None,
                        logo_path=_LOGO_PATH_RPT,
                    )
                st.session_state["pa_phys_report_bytes"] = phys_bytes
                st.success("Physician Report ready - download below.")
            except Exception as e:
                st.error(f"Could not generate Physician Report: {e}")

        if st.session_state.get("pa_phys_report_bytes"):
            st.download_button(
                "⬇ Download Physician Report (.pdf)",
                data=st.session_state["pa_phys_report_bytes"],
                file_name=(
                    f"INEXION_Physician_Report_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                ),
                mime="application/pdf",
                key="dl_phys_rpt",
                use_container_width=True,
            )

    st.markdown("")
    st.caption(
        "Reports generate at the moment you click and reflect the current "
        "values in the input section. Narrative content is written by Claude "
        "Opus 4.6 from the deterministic biomarker data; this takes ~15-30 "
        "seconds per report. If the API key is unavailable the report falls "
        "back to static templates so the deliverable still ships. Both "
        "reports are INEXION-branded with the registry logo, navy + gold "
        "palette, and standard disclaimers."
    )
