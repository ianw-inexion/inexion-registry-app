"""
Research Hypothesis Workbench - test associations without writing Python.

Select exposure, outcome, covariates, and dataset. Get partial correlations,
regression coefficients, and scatter plots. NHANES + HRS + MIDUS.
"""
import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
from numpy.linalg import lstsq
import plotly.express as px
import plotly.graph_objects as go
from src.config import (data_exists, NAVY, GOLD, CORAL, TEAL,
                        NHANES_PARQUET, HRS_VBS_PARQUET, HRS_PUBLIC_PARQUET,
                        MIDUS_BIO_PARQUET, MIDUS_COG_PARQUET)

st.set_page_config(page_title="Research Workbench - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Research Hypothesis Workbench</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Test associations without writing Python - Partial correlations - OLS regression - Scatter plots
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Variable dictionaries per dataset
NHANES_VARS = {
    'phenoage_delta':    'PhenoAge Delta (biological age acceleration, yrs)',
    'phenoage':          'PhenoAge (biological age, yrs)',
    'kdm_advance':       'KDM Biological Age Advance (yrs)',
    'crp':               'CRP - C-Reactive Protein (mg/L)',
    'hba1c':             'HbA1c (%)',
    'albumin':           'Albumin (g/dL)',
    'rdw':               'RDW - Red Cell Distribution Width (%)',
    'wbc':               'WBC - White Blood Cell Count (x1000/uL)',
    'lymphocyte_pct':    'Lymphocyte Percentage (%)',
    'creatinine':        'Creatinine (mg/dL)',
    'alkaline_phosphatase': 'Alkaline Phosphatase (U/L)',
    'mcv':               'MCV - Mean Corpuscular Volume (fL)',
    'hdl':               'HDL Cholesterol (mg/dL)',
    'total_cholesterol': 'Total Cholesterol (mg/dL)',
    'fasting_glucose':   'Fasting Glucose (mg/dL)',
    'bmi':               'BMI (kg/m^2)',
    'systolic_mean':     'Systolic Blood Pressure (mmHg)',
    'diastolic_mean':    'Diastolic Blood Pressure (mmHg)',
    'homa_ir':           'HOMA-IR (insulin resistance)',
    'waist_cm':          'Waist Circumference (cm)',
    'age':               'Age (years)',
    'sex':               'Sex (1=Male, 2=Female)',
    'race_ethnicity':    'Race/Ethnicity',
    'education':         'Education (years)',
    'income_ratio':      'Income-to-Poverty Ratio',
    'cycle_start_year':  'NHANES Cycle Year',
}

HRS_VARS = {
    'phenoage_delta':         'PhenoAge Delta (biological age acceleration, yrs)',
    'phenoage':               'PhenoAge (biological age, yrs)',
    'palb':                   'Albumin (g/dL) - VBS',
    'pcr':                    'Creatinine (mg/dL) - VBS',
    'pgluff':                 'Glucose (mg/dL) - VBS',
    'pcrp':                   'CRP (mg/L) - VBS',
    'plymp':                  'Lymphocyte % - VBS',
    'pmcv':                   'MCV (fL) - VBS',
    'prdw':                   'RDW (%) - VBS',
    'palkp2':                 'Alkaline Phosphatase (U/L) - VBS',
    'pwbc':                   'WBC (x1000/uL) - VBS',
    'r13agey_b':              'Age (years)',
    'ragender':               'Sex (1=Male, 2=Female)',
}

HRS_SURVEY_VARS = {
    'cognitive_total':        'Total Cognitive Score (0-35)',
    'word_recall_immediate':  'Immediate Word Recall (0-20)',
    'serial7_score':          'Serial 7s Score (0-5)',
    'adl_limitations':        'ADL Limitations (0-5)',
    'iadl_limitations':       'IADL Limitations (0-5)',
    'mobility_limitations':   'Mobility Limitations (0-5)',
    'walking_difficulty':     'Walking Difficulty (0/1)',
    'condition_count':        'Chronic Condition Count (0-6)',
    'cesd_depression':        'CESD Depression Score (0-8)',
    'self_rated_health':      'Self-Rated Health (1=excellent, 5=poor)',
    'bmi_self_report':        'BMI (self-report)',
    'age':                    'Age (years)',
    'sex':                    'Sex (Male/Female)',
    'education_years':        'Education (years)',
}

MIDUS_VARS = {
    # Biological age
    'kdm_advance':              'KDM Biological Age Advance (yrs) - MIDUS-anchored',
    'kdm_bioage':               'KDM Biological Age (yrs) - MIDUS-anchored',
    # Inflammation panel (MIDUS distinctive)
    'crp_mg_l':                 'CRP (mg/L)',
    'il6_msd':                  'IL-6 (pg/mL, high-sens MSD)',
    'il8':                      'IL-8 (pg/mL)',
    'il10':                     'IL-10 (pg/mL)',
    'tnf_alpha':                'TNF-alpha (pg/mL)',
    'fibrinogen':               'Fibrinogen (mg/dL)',
    'sicam':                    'sICAM-1 (ng/mL)',
    'seselectin':               'sE-selectin (ng/mL)',
    'supar':                    'sUPAR (ng/mL) - M2 only',
    # Cardiometabolic
    'hba1c_pct':                'HbA1c (%)',
    'glucose_mg_dl':            'Fasting glucose (mg/dL)',
    'homair':                   'HOMA-IR',
    'total_cholesterol':        'Total cholesterol (mg/dL)',
    'hdl':                      'HDL (mg/dL)',
    'ldl':                      'LDL (mg/dL)',
    'triglycerides':            'Triglycerides (mg/dL)',
    'creatinine_mg_dl':         'Creatinine (mg/dL)',
    'egfr':                     'eGFR (mL/min)',
    # Anthropometry / hemodynamics
    'bmi':                      'BMI (kg/m^2)',
    'whr':                      'Waist-hip ratio',
    'systolic_bp_mean':         'Mean systolic BP (mmHg)',
    'diastolic_bp_mean':        'Mean diastolic BP (mmHg)',
    # Neuroendocrine
    'dheas':                    'DHEA-S (ug/dL)',
    'dhea':                     'DHEA (ng/mL)',
    'igf1':                     'IGF-1 (ng/mL)',
    'urinary_cortisol_12h':     'Urinary cortisol 12hr (ug/dL)',
    'urinary_norepi':           'Urinary norepinephrine (ug/dL)',
    'urinary_epi':              'Urinary epinephrine (ug/dL)',
    # Bone turnover
    'p1np':                     'P1NP (bone formation marker)',
    'ntx':                      'NTx (bone resorption marker)',
    'bap':                      'Bone alkaline phosphatase (U/L)',
    # Cognitive (M3 only, joined via M2ID)
    'wordlist_total_unique':    'Word recall (unique items) - M3 BTACT',
    'digit_span_back_score':    'Digit span backward score - M3 BTACT',
    'category_fluency_unique':  'Category fluency (unique) - M3 BTACT',
    'number_series_first_pass': 'Number series first pass - M3 BTACT',
    # Demographics
    'age':                      'Age (years)',
    'sex':                      'Sex (M/F)',
    'wave':                     'MIDUS wave (M2 / Refresher1 / M3)',
}

# Data loaders
@st.cache_data
def load_nhanes():
    return pd.read_parquet(NHANES_PARQUET) if data_exists(NHANES_PARQUET) else pd.DataFrame()

@st.cache_data
def load_hrs_vbs():
    if not data_exists(HRS_VBS_PARQUET):
        return pd.DataFrame()
    vbs = pd.read_parquet(HRS_VBS_PARQUET)
    survey = pd.read_parquet(HRS_PUBLIC_PARQUET) if data_exists(HRS_PUBLIC_PARQUET) else pd.DataFrame()
    if not survey.empty:
        cog_cols = ['respondent_id','cognitive_total','word_recall_immediate',
                    'serial7_score','adl_limitations','iadl_limitations',
                    'mobility_limitations','walking_difficulty','condition_count',
                    'cesd_depression','self_rated_health','bmi_self_report',
                    'education_years']
        cog = survey[[c for c in cog_cols if c in survey.columns]].rename(
            columns={'respondent_id':'hhidpn'})
        vbs = vbs.merge(cog, on='hhidpn', how='left')
    return vbs

@st.cache_data
def load_midus():
    """Biomarker stack with optional left-join to M3 cognitive."""
    if not data_exists(MIDUS_BIO_PARQUET):
        return pd.DataFrame()
    bio = pd.read_parquet(MIDUS_BIO_PARQUET)
    # Coerce sex to numeric for OLS-friendliness (M=1, F=2 to match other sheets)
    bio['sex'] = bio['sex'].map({'M': 1, 'F': 2})
    # Coerce merge key to plain object string regardless of dtype the parquet was written with
    if 'midus_id' in bio.columns:
        bio['midus_id'] = bio['midus_id'].astype(str)
    if data_exists(MIDUS_COG_PARQUET):
        cog = pd.read_parquet(MIDUS_COG_PARQUET)
        cog_cols = ['midus_id','wordlist_total_unique','wordlist_total_repeats',
                    'digit_span_back_score','category_fluency_unique',
                    'number_series_total','number_series_first_pass']
        cog = cog[[c for c in cog_cols if c in cog.columns]].copy()
        if 'midus_id' in cog.columns:
            cog['midus_id'] = cog['midus_id'].astype(str)
        bio = bio.merge(cog, on='midus_id', how='left')
    return bio

nhanes = load_nhanes()
hrs    = load_hrs_vbs()
midus  = load_midus()

# UI
col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("### Hypothesis Setup")

    dataset = st.selectbox(
        "Dataset",
        ["NHANES 2001-2018", "HRS 2016 (VBS + Survey)", "MIDUS (M2 + R1 + M3, 2004-2022)"],
    )
    if dataset.startswith("NHANES"):
        df = nhanes
        var_dict = {**NHANES_VARS}
    elif dataset.startswith("HRS"):
        df = hrs
        var_dict = {**HRS_VARS, **HRS_SURVEY_VARS}
    else:
        df = midus
        var_dict = {**MIDUS_VARS}

    if df.empty:
        st.error("Selected dataset is not loaded. Check parquet path and data availability.")
        st.stop()

    available = [k for k in var_dict if k in df.columns]
    if not available:
        st.error("No variables from this dataset's dictionary are present in the parquet.")
        st.stop()

    # Pick reasonable default exposures per dataset
    exposure_default = next(
        (v for v in ['phenoage_delta', 'kdm_advance', 'crp_mg_l'] if v in available),
        available[0],
    )
    exposure_key = st.selectbox(
        "Exposure (X)", available,
        index=available.index(exposure_default),
        format_func=lambda k: var_dict[k],
    )

    outcome_options = [k for k in available if k != exposure_key]
    default_outcome_candidates = [
        'cognitive_total', 'wordlist_total_unique', 'hba1c', 'hba1c_pct'
    ]
    default_outcome = next(
        (v for v in default_outcome_candidates if v in outcome_options),
        outcome_options[0],
    )
    outcome_key = st.selectbox(
        "Outcome (Y)", outcome_options,
        index=outcome_options.index(default_outcome),
        format_func=lambda k: var_dict[k],
    )

    covariate_options = [k for k in available if k not in [exposure_key, outcome_key]]
    default_covs = [k for k in
                    ['age','r13agey_b','sex','ragender','education','education_years','wave']
                    if k in covariate_options][:3]
    covariate_keys = st.multiselect(
        "Covariates (control for)",
        covariate_options,
        default=default_covs,
        format_func=lambda k: var_dict.get(k, k),
    )

    age_col_present = next((c for c in ['age','r13agey_b'] if c in df.columns), None)
    if age_col_present:
        age_min = int(df[age_col_present].min())
        age_max = int(df[age_col_present].max())
        age_filter = st.slider("Age range filter", age_min, age_max, (age_min, age_max), key="wb_age")
    else:
        age_filter = (20, 90)

    run = st.button("Run Analysis", type="primary", use_container_width=True)

# Analysis
with col_right:
    if not run:
        st.info("Configure your hypothesis on the left and click **Run Analysis**.")
        st.markdown(
            "**How to use:**\n\n"
            "Select an exposure variable (what you think is causing something), "
            "an outcome variable (what you're measuring), and covariates to control for. "
            "The workbench computes the unadjusted and adjusted associations and shows "
            "the scatter plot.\n\n"
            "**Example hypotheses:**\n"
            "- NHANES: Does PhenoAge delta predict HbA1c, controlling for age and sex?\n"
            "- HRS: Does PhenoAge delta predict cognitive score, controlling for age, sex, education?\n"
            "- MIDUS: Does IL-6 predict KDM advance, controlling for age and sex?\n"
            "- MIDUS: Does inflammation (CRP, IL-6) predict word recall in M3, controlling for age, sex, HbA1c?\n"
            "- MIDUS: Has the inflammation profile shifted across waves (control for age)?"
        )
    else:
        # Build analytic dataset
        age_col = 'age' if 'age' in df.columns else 'r13agey_b'
        cols_needed = list({exposure_key, outcome_key, age_col} | set(covariate_keys))
        analytic = df[[c for c in cols_needed if c in df.columns]].copy()

        # Coerce wave to numeric ordinal if it's in the analytic frame (MIDUS)
        if 'wave' in analytic.columns:
            analytic['wave'] = analytic['wave'].map(
                {'MIDUS2': 1, 'MIDUS_Refresher1': 2, 'MIDUS3': 3}
            )

        analytic = analytic.dropna()

        # Age filter
        if age_col in analytic.columns:
            analytic = analytic[analytic[age_col].between(*age_filter)]

        # Coerce all to numeric
        for c in cols_needed:
            if c in analytic.columns:
                analytic[c] = pd.to_numeric(analytic[c], errors='coerce')
        analytic = analytic.dropna()
        n = len(analytic)

        if n < 30:
            st.error(f"Too few observations after filtering: n={n}. Relax filters or choose different variables.")
        else:
            x = analytic[exposure_key].values
            y = analytic[outcome_key].values

            r_raw, p_raw = stats.pearsonr(x, y)

            def residualize(vec, covs):
                if len(covs) == 0:
                    return vec - vec.mean()
                X_cov = np.column_stack([np.ones(len(covs[0]))] + covs)
                beta, _, _, _ = lstsq(X_cov, vec, rcond=None)
                return vec - X_cov @ beta

            cov_arrays = [analytic[c].values for c in covariate_keys if c in analytic.columns]
            rx = residualize(x, cov_arrays)
            ry = residualize(y, cov_arrays)
            r_adj, p_adj = stats.pearsonr(rx, ry)

            X_reg = np.column_stack([np.ones(n), x] + cov_arrays)
            beta_reg, _, _, _ = lstsq(X_reg, y, rcond=None)
            y_pred = X_reg @ beta_reg
            ss_res = np.sum((y - y_pred)**2)
            ss_tot = np.sum((y - y.mean())**2)
            r2 = 1 - ss_res / ss_tot

            st.markdown(f"**n = {n:,}** analytic observations | {dataset}")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Unadjusted r", f"{r_raw:.3f}")
            m2.metric("p-value (unadj.)", f"{p_raw:.2e}")
            m3.metric("Partial r (adjusted)", f"{r_adj:.3f}")
            m4.metric("p-value (adj.)", f"{p_adj:.2e}")

            reg_names = ['Intercept', var_dict.get(exposure_key, exposure_key)] + \
                        [var_dict.get(c, c) for c in covariate_keys if c in analytic.columns]
            reg_df = pd.DataFrame({
                'Variable': reg_names,
                'Coefficient': [f"{b:.4f}" for b in beta_reg],
            })
            reg_df.loc[len(reg_df)] = ['R^2', f"{r2:.4f}"]
            st.markdown("**OLS Regression Coefficients**")
            st.dataframe(reg_df, width='stretch', key='wb_reg_table')

            plot_df = pd.DataFrame({
                var_dict.get(exposure_key, exposure_key): x,
                var_dict.get(outcome_key, outcome_key): y,
            })
            fig = px.scatter(
                plot_df,
                x=var_dict.get(exposure_key, exposure_key),
                y=var_dict.get(outcome_key, outcome_key),
                opacity=0.3,
                color_discrete_sequence=[NAVY],
                title=f"{var_dict.get(exposure_key, exposure_key)} vs {var_dict.get(outcome_key, outcome_key)}",
            )
            x_line = np.linspace(x.min(), x.max(), 100)
            y_line = beta_reg[0] + beta_reg[1] * x_line
            fig.add_trace(go.Scatter(
                x=x_line, y=y_line, mode='lines',
                line=dict(color=CORAL, width=2),
                name=f'OLS fit (r={r_raw:.3f})',
            ))
            fig.update_layout(
                plot_bgcolor='white', paper_bgcolor='white',
                font_color='#1A1A2E', height=420,
            )
            st.plotly_chart(fig, width='stretch', key='wb_scatter')

            st.caption(
                f"Unadjusted Pearson r = {r_raw:.3f} (p = {p_raw:.2e}). "
                f"Partial r controlling for [{', '.join([var_dict.get(c,c) for c in covariate_keys])}] "
                f"= {r_adj:.3f} (p = {p_adj:.2e}). "
                f"OLS R^2 = {r2:.3f}. n = {n:,}."
            )
