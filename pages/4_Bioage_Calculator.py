"""
Biological Age Calculator — paste lab values or upload a PDF lab report.

Features:
- PDF lab report upload → Claude API extraction → auto-populate inputs
- Sex field (required for KDM; optional for PhenoAge percentile stratification)
- PhenoAge computation (Levine 2018) with delta and 10-year mortality risk
- All computation is local — no patient data persists beyond the session
"""
import io
import json
import os
import streamlit as st
import plotly.graph_objects as go
from src.bioage import compute_phenoage
from src.config import NAVY, GOLD, CORAL, TEAL

st.set_page_config(page_title="Bioage Calculator — INEXION Registry", layout="wide")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style='padding: 18px 24px; background: {NAVY}; border-radius: 8px;
                margin-bottom: 20px;'>
        <div style='color: {GOLD}; font-size: 12px; letter-spacing: 2px;
                    text-transform: uppercase; font-weight: 600;'>
            INEXION Longevity Registry
        </div>
        <div style='color: white; font-size: 26px; font-weight: 700;
                    margin-top: 4px;'>Biological Age Calculator</div>
        <div style='color: #C9CBD4; font-size: 13px; margin-top: 6px;'>
            Levine 2018 PhenoAge algorithm · Validated against the BioAge R
            package (r = 0.91 on NHANES 2017–2018)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Session state defaults ────────────────────────────────────────────────────
DEFAULTS = {
    "albumin":   4.3,
    "creatinine": 0.9,
    "glucose":   95.0,
    "crp":        1.5,
    "lymph":     30.0,
    "mcv":       90.0,
    "rdw":       13.0,
    "alkphos":   70.0,
    "wbc":        6.5,
    "extract_msg": "",
    "extract_ok":  False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── PDF extraction ────────────────────────────────────────────────────────────
def extract_labs_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Extract the 9 PhenoAge biomarker values from a PDF lab report.
    Uses pdfplumber to pull text, then calls the Claude API to parse values.
    Returns a dict with keys matching session state names, plus 'message'.
    """
    try:
        import pdfplumber
    except ImportError:
        return {"message": "pdfplumber not installed. Run: pip install pdfplumber", "ok": False}

    try:
        import anthropic
    except ImportError:
        return {"message": "anthropic not installed. Run: pip install anthropic", "ok": False}

    # Extract text from all pages
    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)

    if not text_pages:
        return {"message": "Could not extract text from this PDF. Try a text-based lab report rather than a scanned image.", "ok": False}

    lab_text = "\n".join(text_pages)[:8000]  # cap at 8K chars — plenty for a lab report

    # Claude extraction prompt
    system_prompt = (
        "You are a clinical lab report parser. Extract specific biomarker values from the "
        "provided lab report text and return them as a JSON object. "
        "Return ONLY valid JSON — no explanation, no markdown, no code fences. "
        "If a value is not found or ambiguous, use null. "
        "All values must be in the units specified."
    )

    user_prompt = f"""Extract the following biomarker values from this lab report.
Return a JSON object with exactly these keys and units:

{{
  "albumin": <float, g/dL>,
  "creatinine": <float, mg/dL>,
  "glucose": <float, mg/dL — use fasting glucose if available>,
  "crp": <float, mg/L — C-reactive protein; if reported as mg/dL multiply by 10>,
  "lymph": <float, % — lymphocyte percentage>,
  "mcv": <float, fL — mean corpuscular volume>,
  "rdw": <float, % — red cell distribution width>,
  "alkphos": <float, U/L — alkaline phosphatase>,
  "wbc": <float, ×1000/µL or K/µL — white blood cell count>
}}

Lab report text:
{lab_text}"""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "message": "ANTHROPIC_API_KEY not set in environment. Add it to your .env or Streamlit secrets.",
            "ok": False,
        }

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])

        extracted = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"message": f"Could not parse extraction response: {e}", "ok": False}
    except Exception as e:
        return {"message": f"Extraction error: {e}", "ok": False}

    # Populate session state for any non-null values found
    field_map = {
        "albumin": ("albumin", 2.5, 6.0),
        "creatinine": ("creatinine", 0.3, 5.0),
        "glucose": ("glucose", 50.0, 400.0),
        "crp": ("crp", 0.01, 50.0),
        "lymph": ("lymph", 5.0, 80.0),
        "mcv": ("mcv", 70.0, 110.0),
        "rdw": ("rdw", 10.0, 25.0),
        "alkphos": ("alkphos", 20.0, 400.0),
        "wbc": ("wbc", 2.0, 20.0),
    }

    found = []
    missing = []
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
            msg += f" Not found: {', '.join(missing)}. Enter these manually."
        return {"message": msg, "ok": True}
    else:
        return {
            "message": "No biomarker values could be extracted. The report may be image-based or use non-standard formatting. Enter values manually.",
            "ok": False,
        }


# ── Lab report upload ─────────────────────────────────────────────────────────
with st.expander("📄 Upload lab report to auto-populate values", expanded=False):
    st.caption(
        "Upload a PDF lab report (Quest, LabCorp, hospital, or equivalent). "
        "Values will be extracted automatically and pre-filled below. "
        "Review all values before calculating — always verify against your original report."
    )
    uploaded = st.file_uploader(
        "Lab report PDF", type=["pdf"], label_visibility="collapsed"
    )
    if uploaded is not None:
        with st.spinner("Extracting lab values…"):
            result = extract_labs_from_pdf(uploaded.read())
            st.session_state["extract_msg"] = result["message"]
            st.session_state["extract_ok"] = result.get("ok", False)

    if st.session_state["extract_msg"]:
        if st.session_state["extract_ok"]:
            st.success(st.session_state["extract_msg"])
        else:
            st.warning(st.session_state["extract_msg"])

st.divider()

# ── Input fields ──────────────────────────────────────────────────────────────
st.caption(
    "Values pre-populated from your lab report are shown below. "
    "Review and adjust before calculating. All units match NHANES-standard reporting."
)

demo_col, _, _ = st.columns([1, 1, 1])
with demo_col:
    age = st.number_input("Age (years)", 18, 100, 50)
    sex = st.selectbox("Sex", ["Male", "Female"], help="Required for KDM algorithm and percentile stratification. Not used in PhenoAge computation.")

c1, c2, c3 = st.columns(3)
with c1:
    albumin  = st.number_input("Albumin (g/dL)",             2.5,  6.0,  st.session_state["albumin"],   step=0.1,  key="albumin")
    creatinine = st.number_input("Creatinine (mg/dL)",        0.3,  5.0,  st.session_state["creatinine"], step=0.1,  key="creatinine")
    glucose  = st.number_input("Glucose (mg/dL)",            50.0, 400.0, st.session_state["glucose"],   step=1.0,  key="glucose")
with c2:
    crp      = st.number_input("CRP (mg/L)",                 0.01, 50.0,  st.session_state["crp"],       step=0.1,  key="crp")
    lymph    = st.number_input("Lymphocyte %",               5.0,  80.0,  st.session_state["lymph"],     step=0.5,  key="lymph")
    mcv      = st.number_input("MCV (fL)",                   70.0, 110.0, st.session_state["mcv"],       step=0.5,  key="mcv")
with c3:
    rdw      = st.number_input("RDW (%)",                    10.0, 25.0,  st.session_state["rdw"],       step=0.1,  key="rdw")
    alkphos  = st.number_input("Alkaline phosphatase (U/L)", 20.0, 400.0, st.session_state["alkphos"],   step=1.0,  key="alkphos")
    wbc      = st.number_input("WBC (×1000/µL)",             2.0,  20.0,  st.session_state["wbc"],       step=0.1,  key="wbc")

# ── Compute ───────────────────────────────────────────────────────────────────
if st.button("Calculate biological age", type="primary", use_container_width=True):
    r = compute_phenoage(
        age=age,
        albumin_g_dl=albumin,
        creatinine_mg_dl=creatinine,
        glucose_mg_dl=glucose,
        crp_mg_l=crp,
        lymphocyte_pct=lymph,
        mcv_fl=mcv,
        rdw_pct=rdw,
        alk_phos_u_l=alkphos,
        wbc_1000_ul=wbc,
    )
    pa    = r["phenoage"]
    delta = r["delta"]
    mort  = r["mortality_10y"]

    delta_color = TEAL if delta <= 0 else CORAL
    delta_label = "biologically younger" if delta <= 0 else "biologically older"

    st.markdown(
        f"""
        <div style='background:{NAVY}; color:white; padding:28px;
                    border-radius:10px; text-align:center; margin-top:20px;'>
            <div style='color:{GOLD}; font-size:12px; letter-spacing:2px;
                        text-transform:uppercase;'>PhenoAge result</div>
            <div style='font-size:56px; font-weight:800; margin-top:6px;'>
                {pa:.1f} <span style='color:{GOLD}; font-size:28px;'>years</span>
            </div>
            <div style='font-size:18px; color:{delta_color}; margin-top:8px; font-weight:600;'>
                {delta:+.1f} years — {delta_label} than chronological age
            </div>
            <div style='font-size:13px; color:#C9CBD4; margin-top:14px;'>
                Estimated 10-year mortality risk (Gompertz model): {mort * 100:.2f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=["Chronological", "Biological (PhenoAge)"],
        x=[age, pa],
        orientation="h",
        marker_color=[GOLD, NAVY],
        text=[f"{age} yr", f"{pa:.1f} yr"],
        textposition="outside",
    ))
    fig.update_layout(
        height=220,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font_color="#1A1A2E",
        showlegend=False,
        xaxis=dict(range=[0, max(age, pa) * 1.25], title="Age (years)"),
        margin=dict(t=20, b=40, l=40, r=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "PhenoAge is a research instrument validated on NHANES population data (Levine et al., 2018). "
        "It is not a clinical diagnostic. A +3 year delta means biomarkers statistically resemble "
        "those of a 3-year-older population mean — not that any individual 'is' biologically 3 years older. "
        f"Sex recorded: {sex} (used for KDM stratification when that algorithm is added)."
    )
