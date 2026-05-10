"""
Research Hypothesis Workbench - test associations without writing Python.

Models supported:
  - OLS (linear regression with partial correlation)
  - Cox PH (univariate / age-adjusted survival)
  - Logistic (binary outcomes - OR + AUC)
  - Mixed-effects (random-intercept linear model for longitudinal data)
  - GAM (smooth term on the exposure with optional linear covariates)

All five models append to a uniform session log that supports BH-FDR
correction across heterogeneous tests.
"""
import time
import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
from numpy.linalg import lstsq
import plotly.express as px
import plotly.graph_objects as go
from src.config import (data_exists, NAVY, GOLD, CORAL, TEAL,
                        NHANES_PARQUET, HRS_VBS_PARQUET, HRS_PUBLIC_PARQUET,
                        HRS_DBS_PARQUET, NHANES_MORTALITY_PARQUET,
                        MIDUS_BIO_PARQUET, MIDUS_COG_PARQUET,
                        NSHAP_BIO_PARQUET, NSHAP_SOCIAL_PARQUET,
                        GEO_PANEL_PARQUET,
                        CLINIC_WORKBENCH_PARQUET)

st.set_page_config(page_title="Research Workbench - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Research Hypothesis Workbench</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            OLS - Cox PH - Logistic - Mixed-effects - GAM &nbsp;|&nbsp;
            BH-FDR session log
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ===========================================================================
# Variable dictionaries
# ===========================================================================
NHANES_VARS = {
    'phenoage_delta':    'PhenoAge Delta (yrs)',
    'phenoage':          'PhenoAge (yrs)',
    'kdm_advance':       'KDM Biological Age Advance (yrs)',
    'liver_advance':     'Liver Age advance (yrs)',
    'kidney_advance':    'Kidney Age advance (yrs)',
    'metabolic_advance': 'Metabolic Age advance (yrs)',
    'crp':               'CRP (mg/L)',
    'hba1c':             'HbA1c (%)',
    'albumin':           'Albumin (g/dL)',
    'rdw':               'RDW (%)',
    'wbc':               'WBC (x1000/uL)',
    'lymphocyte_pct':    'Lymphocyte %',
    'creatinine':        'Creatinine (mg/dL)',
    'alkaline_phosphatase': 'Alkaline Phosphatase (U/L)',
    'mcv':               'MCV (fL)',
    'hdl':               'HDL Cholesterol (mg/dL)',
    'total_cholesterol': 'Total Cholesterol (mg/dL)',
    'fasting_glucose':   'Fasting Glucose (mg/dL)',
    'bmi':               'BMI (kg/m^2)',
    'systolic_mean':     'Systolic BP (mmHg)',
    'diastolic_mean':    'Diastolic BP (mmHg)',
    'homa_ir':           'HOMA-IR',
    'waist_cm':          'Waist Circumference (cm)',
    'egfr':              'eGFR (CKD-EPI 2021)',
    'age':               'Age (years)',
    'sex':               'Sex (1=M, 2=F)',
    'race_ethnicity':    'Race/Ethnicity',
    'education':         'Education (years)',
    'income_ratio':      'Income-to-Poverty Ratio',
    'cycle_start_year':  'NHANES Cycle Year',
    'mortality_status':  'Mortality status (0/1)',
    'years_to_event':    'Years to event (or censor)',
}

HRS_VARS = {
    'phenoage_delta':         'PhenoAge Delta (yrs)',
    'phenoage':               'PhenoAge (yrs)',
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
    'ragender':               'Sex (1=M, 2=F)',
    'mortality_status':       'Mortality status (0/1)',
    'years_to_event':         'Years to event',
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
    'self_rated_health':      'Self-Rated Health (1-5)',
    'bmi_self_report':        'BMI (self-report)',
    'age':                    'Age (years)',
    'sex':                    'Sex (Male/Female)',
    'education_years':        'Education (years)',
    'current_smoker':         'Current smoker (0/1)',
    'ever_smoked':            'Ever smoked (0/1)',
    'hypertension':           'Hypertension (0/1)',
    'diabetes':               'Diabetes (0/1)',
    'heart_disease':          'Heart disease (0/1)',
    'stroke':                 'Stroke (0/1)',
    'arthritis':              'Arthritis (0/1)',
    'lung_disease':           'Lung disease (0/1)',
}

DBS_VARS = {
    'hhidpn':     'Respondent ID (grouping)',
    'wave_year':  'Wave year',
    'hba1c':      'HbA1c (%)',
    'crp':        'CRP (mg/L)',
    'hdl':        'HDL (mg/dL)',
    'total_chol': 'Total Cholesterol (mg/dL)',
    'cystatin_c': 'Cystatin-C (mg/L)',
}

MIDUS_VARS = {
    'kdm_advance':              'KDM Biological Age Advance (yrs)',
    'kdm_bioage':               'KDM Biological Age (yrs)',
    'inflammation_advance':     'Inflammation Age advance (yrs)',
    'kidney_advance':           'Kidney Age advance (yrs)',
    'metabolic_advance':        'Metabolic Age advance (yrs)',
    'crp_mg_l':                 'CRP (mg/L)',
    'il6_msd':                  'IL-6 (pg/mL, MSD)',
    'il8':                      'IL-8 (pg/mL)',
    'il10':                     'IL-10 (pg/mL)',
    'tnf_alpha':                'TNF-alpha (pg/mL)',
    'fibrinogen':               'Fibrinogen (mg/dL)',
    'sicam':                    'sICAM-1 (ng/mL)',
    'seselectin':               'sE-selectin (ng/mL)',
    'hba1c_pct':                'HbA1c (%)',
    'glucose_mg_dl':            'Fasting glucose (mg/dL)',
    'homair':                   'HOMA-IR',
    'total_cholesterol':        'Total cholesterol (mg/dL)',
    'hdl':                      'HDL (mg/dL)',
    'ldl':                      'LDL (mg/dL)',
    'triglycerides':            'Triglycerides (mg/dL)',
    'creatinine_mg_dl':         'Creatinine (mg/dL)',
    'egfr':                     'eGFR (mL/min)',
    'bmi':                      'BMI (kg/m^2)',
    'whr':                      'Waist-hip ratio',
    'systolic_bp_mean':         'Mean systolic BP (mmHg)',
    'diastolic_bp_mean':        'Mean diastolic BP (mmHg)',
    'wordlist_total_unique':    'Word recall - M3 BTACT',
    'digit_span_back_score':    'Digit span backward - M3 BTACT',
    'category_fluency_unique':  'Category fluency - M3 BTACT',
    'age':                      'Age (years)',
    'sex':                      'Sex (M/F)',
    'wave':                     'MIDUS wave',
    'mortality_status':         'Mortality status (0/1)',
    'years_to_event':           'Years to event',
}

NSHAP_VARS = {
    'nshap_id':         'NSHAP respondent ID',
    'age':              'Age (years)',
    'sex':              'Sex (1=M, 2=F)',
    'race_ethnicity':   'Race / Ethnicity (1=NH White, 2=NH Black, 3=Hispanic, 4=Other)',
    'education':        'Education (1=<HS, 2=HS, 3=Some college, 4=BA+)',
    'weight_adj':       'NSHAP survey weight (normalized)',
    # Anthropometry / vitals
    'bmi':              'Body Mass Index (kg/m^2)',
    'height_cm':        'Height (cm)',
    'weight_kg':        'Weight (kg)',
    'waist_cm':         'Waist circumference (cm)',
    'systolic_mean':    'Systolic BP (mmHg)',
    'diastolic_mean':   'Diastolic BP (mmHg)',
    'pulse_mean':       'Pulse (bpm)',
    # Blood biomarkers (R1+R2 only - R3 biomarkers pending)
    'hba1c_pct':        'HbA1c (%)',
    'crp_mg_l':         'CRP (mg/L)',
    'ebv_titer':        'EBV antibody titer',
    'hemoglobin':       'Hemoglobin (g/dL)',
    'a1c_whbl':         'HbA1c, whole blood (%)',
    'crp_plsm':         'CRP, plasma (mg/L)',
    # Saliva
    'dhea_1':           'DHEA, sample 1 (saliva)',
    'dhea_2':           'DHEA, sample 2 (saliva)',
    # Network + sensory + functional (from social parquet)
    'network_alters':   'Network size (alters named)',
    'network_close':    'Close confidants (count)',
    'network_close_knit': 'Network closeness (1-5)',
    'hearing':          'Hearing (self-rated, 1-5)',
    'smell':            'Smell test (R1 only)',
    'walk_speed_s':     'Timed walk (seconds)',
    'walk_block':       'Walks 1 block (0=cannot)',
    'walk_room':        'Walks across room (0=cannot)',
    'moca_total':       'MoCA cognitive total (R2-R3)',
    'wave_year':        'Round midpoint year',
    'round':            'NSHAP round',
}

# INEXION Clinic Layer - first-party longitudinal patient registry.
# One row per (patient, visit). registry_patient_id is the grouping
# variable for mixed-effects. The 16 baseline_exposed_<class>
# indicators let researchers run "did exposure to therapeutic class X
# correlate with biological-age trajectory" out of the box.
CLINIC_VARS = {
    # Identifiers & demographics
    'registry_patient_id':          'Patient ID (grouping for mixed-effects)',
    'visit_number':                 'Visit number (1, 2, 3, ...)',
    'age_at_visit':                 'Age at this visit (years)',
    'age_baseline':                 'Age at first visit (years)',
    'sex':                          'Sex',
    'source_clinic':                'Source clinic',
    # Biological-age clocks
    'phenoage':                     'PhenoAge (Levine 2018, years)',
    'phenoage_delta':               'PhenoAge δ vs chronological (years)',
    'phenoage_mortality_10y':       'PhenoAge 10-year mortality risk',
    'liver_age':                    'Liver age (NHANES-trained, years)',
    'liver_age_delta':              'Liver age δ vs chronological (years)',
    'kidney_age':                   'Kidney age (NHANES-trained, years)',
    'kidney_age_delta':             'Kidney age δ vs chronological (years)',
    'phenoage_delta_from_baseline': 'PhenoAge trajectory δ from baseline',
    'liver_age_delta_from_baseline':  'Liver age trajectory δ from baseline',
    'kidney_age_delta_from_baseline': 'Kidney age trajectory δ from baseline',
    # PhenoAge-input labs
    'albumin_g_dL':                 'Albumin (g/dL)',
    'creatinine_mg_dL':             'Creatinine (mg/dL)',
    'glucose_mg_dL':                'Glucose (mg/dL)',
    'crp_cardiac_mg_L':             'hs-CRP (mg/L)',
    'lymphs_pct':                   'Lymphocyte percent (%)',
    'mcv_fL':                       'MCV (fL)',
    'rdw_pct':                      'RDW (%)',
    'alkaline_phosphatase_IU_L':    'Alkaline phosphatase (IU/L)',
    'wbc_x10e3_uL':                 'WBC (x10^3/uL)',
    # Cardiometabolic & CMP highlights
    'hba1c_pct':                    'HbA1c (%)',
    'hdl_mg_dL':                    'HDL cholesterol (mg/dL)',
    'ldl_mg_dL':                    'LDL cholesterol (mg/dL)',
    'triglycerides_mg_dL':          'Triglycerides (mg/dL)',
    'total_cholesterol_mg_dL':      'Total cholesterol (mg/dL)',
    'bun_mg_dL':                    'BUN (mg/dL)',
    'egfr_mL_min_1_73':             'eGFR (mL/min/1.73m^2)',
    'alt_IU_L':                     'ALT (IU/L)',
    'ast_IU_L':                     'AST (IU/L)',
    'bilirubin_total_mg_dL':        'Total bilirubin (mg/dL)',
    'platelets_x10e3_uL':           'Platelets (x10^3/uL)',
    # Hormones & longevity-relevant
    'ferritin_ng_mL':               'Ferritin (ng/mL)',
    'testosterone_total_ng_dL':     'Total testosterone (ng/dL)',
    'igf1_ng_mL':                   'IGF-1 (ng/mL)',
    'tsh_uIU_mL':                   'TSH (uIU/mL)',
    'cortisol_morning_ug_dL':       'Cortisol morning (ug/dL)',
    'uric_acid_mg_dL':              'Uric acid (mg/dL)',
    'vitamin_d_25oh_ng_mL':         '25-OH Vitamin D (ng/mL)',
    # Baseline therapeutic-class exposure indicators (binary 0/1)
    'baseline_exposed_NAD_Pathway':             'Baseline: NAD Pathway',
    'baseline_exposed_mTOR_Modulation':         'Baseline: mTOR Modulation',
    'baseline_exposed_Senolytic':               'Baseline: Senolytic',
    'baseline_exposed_Autophagy':               'Baseline: Autophagy',
    'baseline_exposed_Mitochondrial_Support':   'Baseline: Mitochondrial Support',
    'baseline_exposed_Antioxidant':             'Baseline: Antioxidant',
    'baseline_exposed_Anti_Inflammatory':       'Baseline: Anti-Inflammatory',
    'baseline_exposed_Cognitive_Support':       'Baseline: Cognitive Support',
    'baseline_exposed_Adaptogen':               'Baseline: Adaptogen',
    'baseline_exposed_Methylation_Support':     'Baseline: Methylation Support',
    'baseline_exposed_Vitamin_Mineral':         'Baseline: Vitamin / Mineral',
    'baseline_exposed_Sirtuin_Pathway':         'Baseline: Sirtuin Pathway',
    'baseline_exposed_Hormone_Replacement':     'Baseline: Hormone Replacement',
    'baseline_exposed_Peptide_Therapy':         'Baseline: Peptide Therapy',
    'baseline_exposed_Metabolic':               'Baseline: Metabolic',
    'baseline_exposed_Immune_Modulation':       'Baseline: Immune Modulation',
}


# ===========================================================================
# Stats helpers
# ===========================================================================
def bh_fdr(pvalues):
    """Benjamini-Hochberg FDR-adjusted q-values."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    if m == 0:
        return np.array([], dtype=float)
    # Drop NaN p-values from BH; keep original positions
    valid = np.isfinite(p)
    if not valid.any():
        return np.full_like(p, np.nan)
    p_valid = p[valid]
    order = np.argsort(p_valid)
    ranked = p_valid[order]
    q_sorted = ranked * len(p_valid) / np.arange(1, len(p_valid) + 1)
    q_sorted = np.minimum.accumulate(q_sorted[::-1])[::-1]
    q_valid = np.empty_like(q_sorted)
    q_valid[order] = np.clip(q_sorted, 0.0, 1.0)
    out = np.full_like(p, np.nan)
    out[valid] = q_valid
    return out


# ===========================================================================
# Data loaders
# ===========================================================================
@st.cache_data
def load_nhanes():
    if not data_exists(NHANES_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(NHANES_PARQUET)
    if data_exists(NHANES_MORTALITY_PARQUET):
        m = pd.read_parquet(NHANES_MORTALITY_PARQUET,
                            columns=['seqn', 'years_int_to_event', 'mortality_status'])
        m = m.rename(columns={'years_int_to_event': 'years_to_event'})
        if 'mortality_status' in df.columns:
            df = df.drop(columns=['mortality_status'])
        df = df.merge(m, on='seqn', how='left')
    return df


@st.cache_data
def load_hrs_vbs():
    if not data_exists(HRS_VBS_PARQUET):
        return pd.DataFrame()
    vbs = pd.read_parquet(HRS_VBS_PARQUET)
    survey = pd.read_parquet(HRS_PUBLIC_PARQUET) if data_exists(HRS_PUBLIC_PARQUET) else pd.DataFrame()
    if not survey.empty:
        keep = [c for c in [
            'respondent_id','cognitive_total','word_recall_immediate',
            'serial7_score','adl_limitations','iadl_limitations',
            'mobility_limitations','walking_difficulty','condition_count',
            'cesd_depression','self_rated_health','bmi_self_report',
            'education_years','current_smoker','ever_smoked',
            'hypertension','diabetes','heart_disease','stroke',
            'arthritis','lung_disease',
        ] if c in survey.columns]
        cog = survey[keep].rename(columns={'respondent_id': 'hhidpn'})
        vbs['hhidpn'] = pd.to_numeric(vbs['hhidpn'], errors='coerce')
        cog['hhidpn'] = pd.to_numeric(cog['hhidpn'], errors='coerce')
        vbs = vbs.merge(cog, on='hhidpn', how='left')
    return vbs


@st.cache_data
def load_dbs():
    if not data_exists(HRS_DBS_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(HRS_DBS_PARQUET)


@st.cache_data
def load_midus():
    if not data_exists(MIDUS_BIO_PARQUET):
        return pd.DataFrame()
    bio = pd.read_parquet(MIDUS_BIO_PARQUET)
    bio['sex'] = bio['sex'].map({'M': 1, 'F': 2}) if bio['sex'].dtype == object else bio['sex']
    if 'midus_id' in bio.columns:
        bio['midus_id'] = bio['midus_id'].astype(str)
    if data_exists(MIDUS_COG_PARQUET):
        cog = pd.read_parquet(MIDUS_COG_PARQUET)
        keep = [c for c in [
            'midus_id','wordlist_total_unique','digit_span_back_score',
            'category_fluency_unique','number_series_first_pass',
        ] if c in cog.columns]
        if keep:
            cog = cog[keep].copy()
            cog['midus_id'] = cog['midus_id'].astype(str)
            bio = bio.merge(cog, on='midus_id', how='left')
    return bio


@st.cache_data
def load_nshap():
    """NSHAP biomarker + social merged on (nshap_id, round)."""
    if not data_exists(NSHAP_BIO_PARQUET):
        return pd.DataFrame()
    bio = pd.read_parquet(NSHAP_BIO_PARQUET)
    if data_exists(NSHAP_SOCIAL_PARQUET):
        soc = pd.read_parquet(NSHAP_SOCIAL_PARQUET)
        # Drop overlapping columns from soc before merge so we don't get _x/_y
        overlap = set(bio.columns) & set(soc.columns) - {'nshap_id', 'round'}
        soc = soc.drop(columns=list(overlap))
        bio = bio.merge(soc, on=['nshap_id', 'round'], how='left')
    return bio


@st.cache_data
def load_geo_panel():
    """Pooled-cohort RNA-seq aging panel: rows = samples, cols = (sample_gsm,
    dataset, age, sex, tissue) + 50 z-scored aging gene columns."""
    if not data_exists(GEO_PANEL_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(GEO_PANEL_PARQUET)


@st.cache_data
def load_clinic_workbench():
    """INEXION Clinic Layer flat view: one row per (patient, visit).

    Joined: patients (demographics) x visits (~70 labs) x clocks
    (PhenoAge / Liver / Kidney + deltas + trajectories) + 16 binary
    baseline-exposure indicators (one per therapeutic class).
    Built by inexion_registry.clinic.workbench.build_workbench_table()
    in the pipeline.
    """
    if not data_exists(CLINIC_WORKBENCH_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(CLINIC_WORKBENCH_PARQUET)


# Variable dictionary for the GEO Aging Gene Panel. Entries beyond the
# (age, sex, tissue, dataset) basics are gene symbols whose values are
# z-scored log1p expression within each cohort.
GEO_PANEL_VARS = {
    "age":     "Chronological age (years)",
    "sex":     "Sex",
    "tissue":  "Source tissue",
    "dataset": "Source GEO accession (random-effect grouping for mixed models)",
    # Senescence / SASP
    "CDKN2A":   "CDKN2A / p16 (senescence master regulator)",
    "CDKN1A":   "CDKN1A / p21 (p53 effector, cell-cycle arrest)",
    "GLB1":     "GLB1 / β-galactosidase (senescence marker)",
    "MMP3":     "MMP3 (SASP collagenase)",
    "MMP9":     "MMP9 (SASP gelatinase)",
    "GDF15":    "GDF15 (stress-response cytokine)",
    "SERPINE1": "SERPINE1 / PAI-1 (SASP)",
    "IL6":      "IL6 (SASP cytokine)",
    "IL1B":     "IL1B (SASP cytokine)",
    "TNF":      "TNF (SASP cytokine)",
    # NF-κB / inflammation
    "NFKB1":    "NFKB1 (NF-κB p50 subunit)",
    "NFKB2":    "NFKB2 (NF-κB p52 subunit)",
    "RELA":     "RELA (NF-κB p65 subunit)",
    "CCL2":     "CCL2 / MCP-1 (chemokine)",
    "CXCL8":    "CXCL8 / IL-8 (chemokine)",
    "NLRP3":    "NLRP3 (inflammasome)",
    "PTGS2":    "PTGS2 / COX-2 (inflammation)",
    "CRP":      "CRP (inflammation marker)",
    # Longevity / IGF axis
    "FOXO3":    "FOXO3 (longevity-associated TF)",
    "IGF1":     "IGF1 (insulin-like growth factor 1)",
    "IGF1R":    "IGF1R (IGF-1 receptor)",
    "TERT":     "TERT (telomerase reverse transcriptase)",
    "SIRT1":    "SIRT1 (NAD+-dependent deacetylase)",
    "SIRT3":    "SIRT3 (mitochondrial sirtuin)",
    # Mitochondrial / oxidative stress
    "PPARGC1A": "PPARGC1A / PGC-1α (mitochondrial biogenesis)",
    "TFAM":     "TFAM (mtDNA transcription factor)",
    "NRF1":     "NRF1 (mitochondrial transcription)",
    "SOD1":     "SOD1 (cytoplasmic superoxide dismutase)",
    "SOD2":     "SOD2 (mitochondrial superoxide dismutase)",
    "CAT":      "CAT (catalase)",
    # Muscle / structural
    "LMNA":     "LMNA (lamin A; premature-aging gene)",
    "FBXO32":   "FBXO32 / Atrogin-1 (muscle atrophy)",
    "TRIM63":   "TRIM63 / MuRF1 (muscle atrophy)",
    "MSTN":     "MSTN / myostatin",
    "MYH7":     "MYH7 (slow muscle fiber)",
    "MYH2":     "MYH2 (fast muscle fiber)",
    # DNA damage / repair
    "TP53":     "TP53 (tumor suppressor)",
    "ATM":      "ATM (DNA damage kinase)",
    "BRCA1":    "BRCA1 (DNA repair)",
    "MDM2":     "MDM2 (TP53 negative regulator)",
    "CDKN2B":   "CDKN2B / p15 (cell cycle inhibitor)",
    # Telomere / proliferation
    "TERF1":    "TERF1 (telomere binding)",
    "TERF2":    "TERF2 (telomere binding)",
    "RB1":      "RB1 (retinoblastoma; cell cycle)",
    "CCND1":    "CCND1 (cyclin D1)",
    # Autophagy / proteostasis
    "ATG7":     "ATG7 (autophagy initiation)",
    "MAP1LC3B": "MAP1LC3B / LC3B (autophagosome marker)",
    "BECN1":    "BECN1 / Beclin-1 (autophagy)",
    "MTOR":     "MTOR (mTOR kinase)",
    "SQSTM1":   "SQSTM1 / p62 (autophagy adapter)",
}


nhanes    = load_nhanes()
hrs       = load_hrs_vbs()
dbs       = load_dbs()
midus     = load_midus()
nshap     = load_nshap()
geo_panel = load_geo_panel()
clinic_wb = load_clinic_workbench()

if "wb_log" not in st.session_state:
    st.session_state["wb_log"] = []


# ===========================================================================
# Per-model analysis functions
# ===========================================================================
def _residualize(vec, covs):
    if len(covs) == 0:
        return vec - vec.mean()
    X = np.column_stack([np.ones(len(covs[0]))] + covs)
    beta, *_ = lstsq(X, vec, rcond=None)
    return vec - X @ beta


def run_ols(df, exposure, outcome, covariates):
    sub = df[[exposure, outcome] + covariates].dropna()
    n = len(sub)
    if n < 30:
        return None, "n<30 after dropping NA"
    x = sub[exposure].to_numpy(dtype=float)
    y = sub[outcome].to_numpy(dtype=float)
    cov_arr = [sub[c].to_numpy(dtype=float) for c in covariates]
    rx = _residualize(x, cov_arr)
    ry = _residualize(y, cov_arr)
    r_adj, p_adj = stats.pearsonr(rx, ry)

    X = np.column_stack([np.ones(n), x] + cov_arr)
    beta, *_ = lstsq(X, y, rcond=None)
    y_pred = X @ beta
    ss_res = float(((y - y_pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot
    se = np.sqrt(ss_res / (n - len(beta)) * np.diag(np.linalg.inv(X.T @ X)))
    beta_x = float(beta[1])
    se_x = float(se[1])
    ci_lo, ci_hi = beta_x - 1.96 * se_x, beta_x + 1.96 * se_x

    fig = px.scatter(sub.sample(min(2000, n), random_state=42),
                     x=exposure, y=outcome, opacity=0.3,
                     color_discrete_sequence=[NAVY])
    xs = np.linspace(x.min(), x.max(), 100)
    fig.add_trace(go.Scatter(
        x=xs, y=beta[0] + beta_x * xs, mode='lines',
        line=dict(color=CORAL, width=2.5),
        name=f"OLS fit (β={beta_x:.3f})",
    ))
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=380)
    return {
        "n": n,
        "effect_label": f"β ({exposure})",
        "effect": beta_x, "ci_lo": ci_lo, "ci_hi": ci_hi, "p": float(p_adj),
        "fit_label": "Adjusted R² (partial r)",
        "fit_value": float(r_adj),
        "fit_extra": f"OLS R²={r2:.3f}",
        "fig": fig,
    }, None


def run_cox(df, exposure, covariates):
    try:
        from lifelines import CoxPHFitter
    except ImportError:
        return None, "lifelines not installed"
    needed = [exposure, 'years_to_event', 'mortality_status'] + covariates
    sub = df[needed].dropna()
    sub = sub[sub['years_to_event'] > 0]
    n = len(sub)
    if n < 100 or sub['mortality_status'].sum() < 30:
        return None, f"n={n}, events={int(sub['mortality_status'].sum())} - too few"
    cph = CoxPHFitter()
    try:
        cph.fit(sub, duration_col='years_to_event', event_col='mortality_status')
    except Exception as e:
        return None, f"Cox fit failed: {e}"
    s = cph.summary.loc[exposure]
    cidx = float(cph.concordance_index_)

    # KM by quintile of exposure
    from lifelines import KaplanMeierFitter
    sub2 = sub.copy()
    sub2['q'] = pd.qcut(sub2[exposure], 5, labels=['Q1','Q2','Q3','Q4','Q5'])
    palette = [TEAL, "#7FB069", GOLD, "#E8A85B", CORAL]
    fig = go.Figure()
    for q, color in zip(['Q1','Q2','Q3','Q4','Q5'], palette):
        s_q = sub2[sub2['q'] == q]
        if len(s_q) < 30:
            continue
        kmf = KaplanMeierFitter()
        kmf.fit(s_q['years_to_event'], s_q['mortality_status'], label=str(q))
        sf = kmf.survival_function_
        fig.add_trace(go.Scatter(x=sf.index, y=sf.iloc[:, 0], mode='lines',
                                  name=str(q), line=dict(color=color, width=2.5)))
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=380,
                      xaxis_title='Years', yaxis_title='Survival',
                      yaxis=dict(range=[0.4, 1.01]),
                      title=f'KM survival by quintile of {exposure}')
    return {
        "n": n,
        "effect_label": f"HR per 1-unit {exposure}",
        "effect": float(s["exp(coef)"]),
        "ci_lo": float(s["exp(coef) lower 95%"]),
        "ci_hi": float(s["exp(coef) upper 95%"]),
        "p": float(s["p"]),
        "fit_label": "C-index",
        "fit_value": cidx,
        "fit_extra": f"events={int(sub['mortality_status'].sum()):,}",
        "fig": fig,
    }, None


def run_logistic(df, exposure, outcome, covariates):
    try:
        import statsmodels.api as sm
    except ImportError:
        return None, "statsmodels not installed"
    needed = [exposure, outcome] + covariates
    sub = df[needed].dropna().copy()
    sub[outcome] = pd.to_numeric(sub[outcome], errors='coerce')
    sub = sub.dropna()
    sub[outcome] = (sub[outcome] > 0.5).astype(int)
    n = len(sub)
    if n < 100 or sub[outcome].sum() < 20 or sub[outcome].sum() > n - 20:
        return None, f"n={n}, positives={int(sub[outcome].sum())} - too few or too imbalanced"
    X = sub[[exposure] + covariates].to_numpy(dtype=float)
    X = sm.add_constant(X)
    y = sub[outcome].to_numpy(dtype=int)
    try:
        res = sm.Logit(y, X).fit(disp=False)
    except Exception as e:
        return None, f"Logit failed: {e}"
    coef = float(res.params[1])
    se = float(res.bse[1])
    p = float(res.pvalues[1])
    or_val = float(np.exp(coef))
    or_lo, or_hi = float(np.exp(coef - 1.96 * se)), float(np.exp(coef + 1.96 * se))

    # AUC
    p_pred = res.predict(X)
    try:
        auc = float(_auc(y, p_pred))
    except Exception:
        auc = float('nan')

    # Predicted-probability vs exposure plot (averaging covariates)
    xs = np.linspace(sub[exposure].quantile(0.02), sub[exposure].quantile(0.98), 80)
    cov_means = [sub[c].mean() for c in covariates]
    Xs = np.column_stack([np.ones_like(xs), xs] + [np.full_like(xs, m) for m in cov_means])
    p_curve = res.predict(Xs)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=p_curve, mode='lines',
                              line=dict(color=CORAL, width=3),
                              name='Predicted P(Y=1)'))
    # rug of observed positives/negatives
    pos = sub[sub[outcome] == 1].sample(min(500, sub[outcome].sum()), random_state=42)
    neg = sub[sub[outcome] == 0].sample(min(500, n - int(sub[outcome].sum())), random_state=42)
    fig.add_trace(go.Scatter(x=pos[exposure], y=[1.02] * len(pos), mode='markers',
                              marker=dict(color=NAVY, size=4, symbol='line-ns-open'),
                              showlegend=False))
    fig.add_trace(go.Scatter(x=neg[exposure], y=[-0.02] * len(neg), mode='markers',
                              marker=dict(color=GOLD, size=4, symbol='line-ns-open'),
                              showlegend=False))
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=380,
                      xaxis_title=exposure, yaxis_title=f'P({outcome}=1)',
                      yaxis=dict(range=[-0.05, 1.05]),
                      title=f'Predicted probability of {outcome} vs {exposure}')
    return {
        "n": n,
        "effect_label": f"OR per 1-unit {exposure}",
        "effect": or_val, "ci_lo": or_lo, "ci_hi": or_hi, "p": p,
        "fit_label": "AUC",
        "fit_value": auc,
        "fit_extra": f"positives={int(sub[outcome].sum()):,}",
        "fig": fig,
    }, None


def _auc(y_true, y_score):
    """Simple AUC via Mann-Whitney - no sklearn dependency."""
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float)
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float('nan')
    u, _ = stats.mannwhitneyu(pos, neg, alternative='greater')
    return u / (len(pos) * len(neg))


def run_mixed(df, exposure, outcome, grouping, covariates):
    try:
        from statsmodels.regression.mixed_linear_model import MixedLM
    except ImportError:
        return None, "statsmodels not installed"
    needed = [exposure, outcome, grouping] + covariates
    sub = df[needed].dropna()
    n = len(sub)
    n_groups = sub[grouping].nunique()
    if n < 200 or n_groups < 30:
        return None, f"n={n}, groups={n_groups} - too few"
    formula_rhs = " + ".join([exposure] + covariates) if covariates else exposure
    try:
        md = MixedLM.from_formula(f"{outcome} ~ {formula_rhs}",
                                    groups=sub[grouping].astype(str), data=sub)
        res = md.fit(method='lbfgs', reml=True)
    except Exception as e:
        return None, f"MixedLM failed: {e}"
    if exposure not in res.params.index:
        return None, "exposure not in fit"
    beta = float(res.params[exposure])
    se = float(res.bse[exposure])
    p = float(res.pvalues[exposure])
    ci_lo, ci_hi = beta - 1.96 * se, beta + 1.96 * se
    sigma2_g = float(res.cov_re.iloc[0, 0]) if hasattr(res.cov_re, "iloc") else float(np.array(res.cov_re).flatten()[0])
    sigma2_e = float(res.scale)
    icc = sigma2_g / (sigma2_g + sigma2_e) if (sigma2_g + sigma2_e) > 0 else float('nan')

    # Spaghetti plot: trajectories of a sample of groups + population fitted line
    sample_groups = sub[grouping].drop_duplicates().sample(min(60, n_groups), random_state=42)
    spag = sub[sub[grouping].isin(sample_groups)].sort_values([grouping, exposure])
    fig = go.Figure()
    for _, traj in spag.groupby(grouping):
        if len(traj) < 2:
            continue
        fig.add_trace(go.Scatter(
            x=traj[exposure], y=traj[outcome],
            mode='lines+markers',
            line=dict(color=NAVY, width=1),
            marker=dict(color=NAVY, size=4),
            opacity=0.25,
            showlegend=False,
        ))
    xs = np.linspace(sub[exposure].min(), sub[exposure].max(), 60)
    yhat = float(res.params['Intercept']) + beta * xs
    fig.add_trace(go.Scatter(x=xs, y=yhat, mode='lines',
                              line=dict(color=CORAL, width=4),
                              name=f'Population fixed-effect (β={beta:.3f})'))
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=420,
                      xaxis_title=exposure, yaxis_title=outcome,
                      title=f'Mixed-effects: {outcome} ~ {exposure} | random({grouping})')
    return {
        "n": n,
        "effect_label": f"β fixed ({exposure})",
        "effect": beta, "ci_lo": ci_lo, "ci_hi": ci_hi, "p": p,
        "fit_label": "ICC (group var / total var)",
        "fit_value": icc,
        "fit_extra": f"groups={n_groups:,}, σ²_g={sigma2_g:.3f}, σ²_e={sigma2_e:.3f}",
        "fig": fig,
    }, None


def run_gam(df, exposure, outcome, covariates):
    try:
        from statsmodels.gam.api import BSplines, GLMGam
        import statsmodels.api as sm
    except ImportError:
        return None, "statsmodels not installed"
    needed = [exposure, outcome] + covariates
    sub = df[needed].dropna()
    n = len(sub)
    if n < 200:
        return None, f"n={n} - too few"
    x = sub[exposure].to_numpy(dtype=float).reshape(-1, 1)
    bs = BSplines(x, df=[8], degree=[3])
    Xc = sub[covariates].to_numpy(dtype=float) if covariates else np.zeros((n, 0))
    Xc = sm.add_constant(np.column_stack([Xc])) if covariates else np.ones((n, 1))
    y = sub[outcome].to_numpy(dtype=float)
    try:
        gam = GLMGam(y, exog=Xc, smoother=bs).fit()
    except Exception as e:
        return None, f"GAM fit failed: {e}"

    # F-test on smooth term
    try:
        f_test = gam.test_significance(smooth_index=0)
        p_smooth = float(f_test.pvalue)
        edf = float(gam.edf[len(Xc[0]):].sum()) if hasattr(gam, "edf") else float('nan')
    except Exception:
        # Fallback: compare with no-smooth GLM
        try:
            base = sm.GLM(y, Xc).fit()
            ll_full = float(gam.llf)
            ll_base = float(base.llf)
            df_diff = max(1, len(gam.params) - len(base.params))
            from scipy.stats import chi2
            lr = 2 * (ll_full - ll_base)
            p_smooth = float(1 - chi2.cdf(lr, df_diff))
            edf = float(df_diff)
        except Exception as e2:
            return None, f"GAM significance test failed: {e2}"

    # Partial-effect plot (smooth on exposure, with 95% CI band)
    grid = np.linspace(sub[exposure].quantile(0.01), sub[exposure].quantile(0.99), 80).reshape(-1, 1)
    bs_grid = bs.transform(grid)
    Xc_grid = np.tile(Xc.mean(axis=0), (len(grid), 1)) if Xc.shape[1] > 0 else np.zeros((len(grid), 0))
    X_grid = np.column_stack([Xc_grid, bs_grid])
    y_pred = X_grid @ gam.params
    pred_se = np.sqrt(np.diag(X_grid @ gam.cov_params() @ X_grid.T))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=grid.flatten(), y=y_pred + 1.96 * pred_se,
        mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(
        x=grid.flatten(), y=y_pred - 1.96 * pred_se,
        mode='lines', fill='tonexty', line=dict(width=0),
        fillcolor='rgba(13,27,62,0.18)', showlegend=False))
    fig.add_trace(go.Scatter(
        x=grid.flatten(), y=y_pred,
        mode='lines', line=dict(color=NAVY, width=3),
        name='GAM smooth (95% CI band)'))
    rug = sub.sample(min(1500, n), random_state=42)
    fig.add_trace(go.Scatter(
        x=rug[exposure], y=rug[outcome],
        mode='markers',
        marker=dict(color=GOLD, size=4, opacity=0.35),
        showlegend=False, name='observed'))
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=420,
                      xaxis_title=exposure, yaxis_title=outcome,
                      title=f'GAM smooth: {outcome} ~ s({exposure})')
    return {
        "n": n,
        "effect_label": f"smooth({exposure}) edf",
        "effect": edf, "ci_lo": float('nan'), "ci_hi": float('nan'), "p": p_smooth,
        "fit_label": "edf (smooth)",
        "fit_value": edf,
        "fit_extra": "F-test on smooth term",
        "fig": fig,
    }, None


# ===========================================================================
# UI
# ===========================================================================
col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown("### Hypothesis Setup")

    dataset = st.selectbox(
        "Dataset",
        ["INEXION Clinic Layer (synthetic_10k)",
         "NHANES 2001-2018", "HRS 2016 (VBS + Survey)",
         "HRS DBS Longitudinal (2006-2016)",
         "MIDUS (M2 + R1 + M3, 2004-2022)",
         "NSHAP (R1 + R2 + R3, 2005-2016)",
         "GEO Aging Gene Panel (pooled RNA-seq, 5 cohorts)"],
        help=(
            "Biomarker cohorts have one row per (subject, wave) with named "
            "biomarker variables. The INEXION Clinic Layer is one row per "
            "(patient, visit) with ~70 lab markers + clocks + 16 binary "
            "baseline-exposure indicators (one per therapeutic class). "
            "Use `registry_patient_id` as the grouping variable for "
            "mixed-effects models when running on clinic data. "
            "The GEO Aging Gene Panel pools samples from "
            "5 RNA-seq cohorts with one row per sample and 50 z-scored "
            "aging-related gene columns. For pooled GEO analyses, mixed-effects "
            "with `dataset` as random intercept is the recommended model "
            "(handles tissue / technology / cohort heterogeneity). The full "
            "15-dataset GEO catalog lives in the GEO Explorer + Pathway "
            "Decomposition pages."
        ),
    )
    if dataset.startswith("INEXION Clinic"):
        df = clinic_wb
        var_dict = {**CLINIC_VARS}
    elif dataset.startswith("NHANES"):
        df = nhanes
        var_dict = {**NHANES_VARS}
    elif dataset.startswith("HRS DBS"):
        df = dbs
        var_dict = {**DBS_VARS}
    elif dataset.startswith("NSHAP"):
        df = nshap
        var_dict = {**NSHAP_VARS}
    elif dataset.startswith("HRS"):
        df = hrs
        var_dict = {**HRS_VARS, **HRS_SURVEY_VARS}
    elif dataset.startswith("GEO"):
        df = geo_panel
        var_dict = {**GEO_PANEL_VARS}
        if not df.empty:
            st.caption(
                f"**{len(df)} samples** across "
                f"{df['dataset'].nunique()} GEO RNA-seq cohorts. "
                "Expression values are z-scored log1p counts within each "
                "cohort. **Recommended model:** Mixed-effects with `dataset` "
                "as random intercept to absorb cross-cohort confounding "
                "(different tissues, technologies, sample-prep protocols)."
            )
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

    model = st.selectbox(
        "Model",
        ["OLS / Linear", "Cox PH (survival)", "Logistic (binary outcome)",
         "Mixed-effects (longitudinal)", "GAM (smooth term on X)"],
    )

    # Exposure
    exp_default = next((v for v in
                        ['phenoage_delta', 'kdm_advance', 'inflammation_advance',
                         'liver_advance', 'wave_year', 'crp_mg_l'] if v in available),
                       available[0])
    exposure_key = st.selectbox(
        "Exposure (X)", available,
        index=available.index(exp_default),
        format_func=lambda k: var_dict[k],
    )

    # Outcome - context-aware
    outcome_key = None
    grouping_key = None

    if model.startswith("Cox"):
        ok = ('mortality_status' in df.columns) and ('years_to_event' in df.columns)
        if not ok:
            st.error("Cox PH requires `mortality_status` and `years_to_event` in the dataset. "
                     "Try NHANES, HRS VBS, or MIDUS biomarker.")
            st.stop()
        st.caption("Outcome: (mortality_status, years_to_event) - auto-fixed.")
    elif model.startswith("Logistic"):
        binary_candidates = []
        for c in df.columns:
            v = pd.to_numeric(df[c], errors='coerce')
            if v.notna().any() and set(v.dropna().unique()).issubset({0.0, 1.0}):
                if df[c].notna().sum() > 200 and v.dropna().nunique() == 2:
                    binary_candidates.append(c)
        binary_in_dict = [c for c in binary_candidates if c in var_dict and c != exposure_key]
        if not binary_in_dict:
            st.error("No binary outcomes available in this dataset.")
            st.stop()
        outcome_key = st.selectbox(
            "Outcome (Y, binary 0/1)", binary_in_dict,
            format_func=lambda k: var_dict.get(k, k),
        )
    elif model.startswith("Mixed"):
        grouping_options = [c for c in [
            'hhidpn', 'midus_id', 'seqn', 'nshap_id',
            'registry_patient_id', 'dataset',
        ] if c in df.columns]
        if not grouping_options:
            st.error("Mixed-effects requires a grouping ID (hhidpn / midus_id). "
                     "Try HRS DBS Longitudinal.")
            st.stop()
        grouping_key = st.selectbox("Grouping ID", grouping_options)
        outcome_options = [k for k in available if k not in [exposure_key, grouping_key]]
        outcome_default = next((v for v in ['hba1c', 'crp', 'hdl'] if v in outcome_options),
                                outcome_options[0])
        outcome_key = st.selectbox(
            "Outcome (Y)", outcome_options,
            index=outcome_options.index(outcome_default),
            format_func=lambda k: var_dict.get(k, k),
        )
    else:  # OLS / GAM
        outcome_options = [k for k in available if k != exposure_key]
        outcome_default = next((v for v in
                                 ['cognitive_total', 'wordlist_total_unique',
                                  'hba1c', 'hba1c_pct', 'crp', 'crp_mg_l'] if v in outcome_options),
                                outcome_options[0])
        outcome_key = st.selectbox(
            "Outcome (Y)", outcome_options,
            index=outcome_options.index(outcome_default),
            format_func=lambda k: var_dict.get(k, k),
        )

    cov_options = [k for k in available
                   if k not in [exposure_key, outcome_key, grouping_key,
                                'mortality_status', 'years_to_event']]
    default_covs = [k for k in
                    ['age', 'r13agey_b', 'sex', 'ragender', 'education',
                     'education_years']
                    if k in cov_options][:3]
    cov_keys = st.multiselect(
        "Covariates (linear adjustments)", cov_options,
        default=default_covs,
        format_func=lambda k: var_dict.get(k, k),
    )

    age_col_present = next((c for c in ['age', 'r13agey_b'] if c in df.columns), None)
    if age_col_present:
        age_min = int(df[age_col_present].min())
        age_max = int(df[age_col_present].max())
        age_filter = st.slider("Age range filter", age_min, age_max, (age_min, age_max), key="wb_age")
    else:
        age_filter = None

    st.markdown("---")
    fdr_alpha = st.slider("FDR threshold (q)", 0.01, 0.20, 0.05, step=0.01, key="wb_fdr_q")
    log_test = st.checkbox("Add this test to session log", value=True, key="wb_log_on")

    run = st.button("Run Analysis", type="primary", use_container_width=True)


# ===========================================================================
# Run
# ===========================================================================
with col_right:
    if not run:
        st.info("Configure your hypothesis on the left and click **Run Analysis**.")
        st.markdown(
            "**Five model types:**\n\n"
            "- **OLS** - linear regression with partial correlation, "
            "for continuous outcomes\n"
            "- **Cox PH** - hazard ratio for time-to-event mortality\n"
            "- **Logistic** - odds ratio for binary outcomes "
            "(cognitive impairment, walking difficulty, conditions...)\n"
            "- **Mixed-effects** - random-intercept linear model for "
            "longitudinal data (HRS DBS waves)\n"
            "- **GAM** - smooth nonlinear term on the exposure with "
            "optional linear covariates\n\n"
            "All five append to a uniform session log. BH-FDR is applied "
            "across all logged tests in this session."
        )
    else:
        # Apply age filter if numeric age column exists
        analytic = df.copy()
        if age_col_present and age_filter:
            analytic = analytic[analytic[age_col_present].between(*age_filter)]

        # Build coerce-to-numeric on relevant columns
        cols_used = [exposure_key] + cov_keys
        if outcome_key:
            cols_used.append(outcome_key)
        if grouping_key:
            cols_used.append(grouping_key)
        if model.startswith("Cox"):
            cols_used += ['mortality_status', 'years_to_event']
        for c in set(cols_used):
            if c in analytic.columns and c != grouping_key:
                analytic[c] = pd.to_numeric(analytic[c], errors='coerce')

        if model.startswith("OLS"):
            res, err = run_ols(analytic, exposure_key, outcome_key, cov_keys)
        elif model.startswith("Cox"):
            res, err = run_cox(analytic, exposure_key, cov_keys)
        elif model.startswith("Logistic"):
            res, err = run_logistic(analytic, exposure_key, outcome_key, cov_keys)
        elif model.startswith("Mixed"):
            res, err = run_mixed(analytic, exposure_key, outcome_key, grouping_key, cov_keys)
        else:  # GAM
            res, err = run_gam(analytic, exposure_key, outcome_key, cov_keys)

        if res is None:
            st.error(f"{model} failed: {err}")
        else:
            n = res["n"]
            st.markdown(f"**n = {n:,}** | {model} | {dataset}")
            m1, m2, m3 = st.columns([2, 2, 2])
            m1.metric(res["effect_label"],
                      f"{res['effect']:+.4f}" if abs(res['effect']) < 100 else f"{res['effect']:.2f}")
            if np.isfinite(res["ci_lo"]) and np.isfinite(res["ci_hi"]):
                m2.metric("95% CI", f"[{res['ci_lo']:+.4f}, {res['ci_hi']:+.4f}]")
            else:
                m2.metric("95% CI", "—")
            m3.metric("p-value", f"{res['p']:.2e}")

            f1, f2 = st.columns([3, 4])
            f1.metric(res["fit_label"], f"{res['fit_value']:.3f}"
                       if isinstance(res['fit_value'], float) and np.isfinite(res['fit_value'])
                       else "—")
            f2.markdown(f"<div style='color:#6B7280;font-size:13px;margin-top:14px;'>"
                        f"{res['fit_extra']}</div>", unsafe_allow_html=True)

            st.plotly_chart(res["fig"], width='stretch', key='wb_main_plot')

            if log_test:
                st.session_state["wb_log"].append({
                    "ts": time.strftime("%H:%M:%S"),
                    "dataset": dataset,
                    "model": model.split(" ")[0],
                    "exposure": var_dict.get(exposure_key, exposure_key),
                    "outcome": var_dict.get(outcome_key, outcome_key) if outcome_key
                               else "(time + event)",
                    "covariates": ", ".join([var_dict.get(c, c) for c in cov_keys]) or "(none)",
                    "n": int(n),
                    "effect_label": res["effect_label"],
                    "effect": float(res["effect"]),
                    "ci_lo": float(res["ci_lo"]),
                    "ci_hi": float(res["ci_hi"]),
                    "p": float(res["p"]),
                    "fit_label": res["fit_label"],
                    "fit_value": float(res["fit_value"])
                                  if isinstance(res["fit_value"], float)
                                     and np.isfinite(res["fit_value"]) else float('nan'),
                })


# ===========================================================================
# Session Log + BH-FDR
# ===========================================================================
st.markdown("---")
st.markdown("### Session log")
log = st.session_state.get("wb_log", [])
if not log:
    st.caption("No tests yet. Each Run with 'Add to session log' enabled is recorded here "
               "so you can apply Benjamini-Hochberg FDR correction across all your tests.")
else:
    log_df = pd.DataFrame(log)
    log_df["q"] = bh_fdr(log_df["p"].values)
    log_df["pass_FDR"] = log_df["q"] <= fdr_alpha

    disp = log_df.copy()
    disp["effect"] = disp["effect"].map(lambda v: f"{v:+.4f}" if abs(v) < 100 else f"{v:.2f}")
    disp["ci"]     = disp.apply(lambda r:
        f"[{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]"
        if np.isfinite(r['ci_lo']) and np.isfinite(r['ci_hi']) else "—", axis=1)
    disp["p"]      = disp["p"].map(lambda v: f"{v:.2e}")
    disp["q"]      = disp["q"].map(lambda v: f"{v:.3e}" if np.isfinite(v) else "—")
    disp["fit_value"] = disp["fit_value"].map(lambda v: f"{v:.3f}" if np.isfinite(v) else "—")
    disp["pass_FDR"] = disp["pass_FDR"].map(lambda b: "yes" if b else "no")
    disp = disp[["ts", "dataset", "model", "exposure", "outcome", "covariates",
                 "n", "effect_label", "effect", "ci", "p", "q", "pass_FDR",
                 "fit_label", "fit_value"]]

    n_tests = len(log_df)
    n_pass  = int(log_df["pass_FDR"].sum())
    cA, cB, cC = st.columns([2, 2, 3])
    cA.metric("Tests this session", f"{n_tests}")
    cB.metric(f"Pass BH-FDR (q ≤ {fdr_alpha:.2f})", f"{n_pass}")
    cC.markdown(
        f"<div style='background:{NAVY};color:white;padding:10px 14px;border-radius:6px;"
        f"font-size:13px;'>q = BH FDR over the p column across all logged tests "
        f"this session, regardless of model type.</div>",
        unsafe_allow_html=True,
    )

    st.dataframe(disp, width='stretch', hide_index=True, key='wb_log_table')

    bcol1, bcol2, bcol3 = st.columns([1, 1, 4])
    with bcol1:
        if st.button("Clear log", key="wb_log_clear"):
            st.session_state["wb_log"] = []
            st.rerun()
    with bcol2:
        csv_bytes = log_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"workbench_session_log_n{len(log_df)}.csv",
            mime="text/csv",
            key="wb_log_dl",
        )

    st.caption(
        "BH-FDR is applied over the p column. Effect, CI, and fit-stat are "
        "model-specific; q-values can change as you add more hypotheses."
    )
