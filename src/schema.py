"""
Variable dictionary for the NHANES harmonized dataset.

Drives the Variable Dictionary page and the Cohort Builder filter controls.
Units are NHANES native unless noted. Categorical encodings match the
harmonizer's canonical values.
"""

# NHANES categorical encodings — harmonizer output values
SEX_LABELS = {1: "Male", 2: "Female"}

RACE_LABELS = {
    1: "Mexican American",
    2: "Other Hispanic",
    3: "Non-Hispanic White",
    4: "Non-Hispanic Black",
    5: "Other / Multi-racial",
}

EDUCATION_LABELS = {
    1: "Less than 9th grade",
    2: "9–11th grade",
    3: "High school grad / GED",
    4: "Some college / AA",
    5: "College graduate or above",
}


# Variable dictionary — grouped for UI
# Each entry: key, label, unit, group, min, max, description
VARIABLES = [
    # Demographics
    {"key": "age", "label": "Age", "unit": "years", "group": "Demographics",
     "min": 0, "max": 85, "description": "Chronological age at NHANES exam."},
    {"key": "sex", "label": "Sex", "unit": "category", "group": "Demographics",
     "description": "1=Male, 2=Female."},
    {"key": "race_ethnicity", "label": "Race / Ethnicity", "unit": "category",
     "group": "Demographics",
     "description": "NHANES 5-level race/ethnicity categorical."},
    {"key": "education", "label": "Education", "unit": "category",
     "group": "Demographics", "description": "NHANES 5-level education category."},
    {"key": "income_ratio", "label": "Family income-to-poverty ratio", "unit": "ratio",
     "group": "Demographics", "min": 0, "max": 5,
     "description": "Ratio of family income to federal poverty threshold. Capped at 5."},

    # Anthropometrics
    {"key": "bmi", "label": "BMI", "unit": "kg/m²", "group": "Anthropometrics",
     "min": 12, "max": 70, "description": "Body mass index."},
    {"key": "waist_cm", "label": "Waist circumference", "unit": "cm",
     "group": "Anthropometrics", "min": 50, "max": 180},
    {"key": "weight_kg", "label": "Weight", "unit": "kg",
     "group": "Anthropometrics", "min": 30, "max": 250},
    {"key": "height_cm", "label": "Height", "unit": "cm",
     "group": "Anthropometrics", "min": 120, "max": 220},

    # Blood pressure
    {"key": "systolic_mean", "label": "Systolic BP (mean)", "unit": "mmHg",
     "group": "Blood pressure", "min": 70, "max": 220,
     "description": "Mean of NHANES systolic readings 2 and 3."},
    {"key": "diastolic_mean", "label": "Diastolic BP (mean)", "unit": "mmHg",
     "group": "Blood pressure", "min": 30, "max": 140},
    {"key": "pulse", "label": "Pulse", "unit": "bpm",
     "group": "Blood pressure", "min": 30, "max": 140},

    # PhenoAge biomarkers (9)
    {"key": "albumin", "label": "Albumin", "unit": "g/dL",
     "group": "PhenoAge biomarkers", "min": 2.5, "max": 6.0,
     "description": "Serum albumin (NHANES units). SI conversion applied in PhenoAge."},
    {"key": "creatinine", "label": "Creatinine", "unit": "mg/dL",
     "group": "PhenoAge biomarkers", "min": 0.2, "max": 15.0},
    {"key": "glucose_biopro", "label": "Glucose (BIOPRO)", "unit": "mg/dL",
     "group": "PhenoAge biomarkers", "min": 40, "max": 500,
     "description": "Non-fasting glucose from biochemistry profile."},
    {"key": "ln_crp", "label": "ln(CRP)", "unit": "ln(mg/L)",
     "group": "PhenoAge biomarkers", "min": -5, "max": 5,
     "description": "Natural log of C-reactive protein."},
    {"key": "crp", "label": "CRP", "unit": "mg/L",
     "group": "PhenoAge biomarkers", "min": 0, "max": 200,
     "description": "C-reactive protein (native scale)."},
    {"key": "lymphocyte_pct", "label": "Lymphocyte %", "unit": "%",
     "group": "PhenoAge biomarkers", "min": 0, "max": 90},
    {"key": "mcv", "label": "Mean cell volume", "unit": "fL",
     "group": "PhenoAge biomarkers", "min": 60, "max": 120},
    {"key": "rdw", "label": "RDW", "unit": "%",
     "group": "PhenoAge biomarkers", "min": 10, "max": 25,
     "description": "Red cell distribution width."},
    {"key": "alkaline_phosphatase", "label": "Alkaline phosphatase", "unit": "U/L",
     "group": "PhenoAge biomarkers", "min": 10, "max": 500},
    {"key": "wbc", "label": "WBC", "unit": "1000/µL",
     "group": "PhenoAge biomarkers", "min": 1, "max": 40},

    # KDM additional biomarkers
    {"key": "total_cholesterol", "label": "Total cholesterol", "unit": "mg/dL",
     "group": "KDM biomarkers", "min": 50, "max": 500},
    {"key": "bun", "label": "BUN", "unit": "mg/dL",
     "group": "KDM biomarkers", "min": 2, "max": 120},
    {"key": "uric_acid", "label": "Uric acid", "unit": "mg/dL",
     "group": "KDM biomarkers", "min": 1, "max": 15},

    # Additional biomarkers
    {"key": "hba1c", "label": "HbA1c", "unit": "%", "group": "Metabolic",
     "min": 3.5, "max": 18},
    {"key": "fasting_glucose", "label": "Fasting glucose", "unit": "mg/dL",
     "group": "Metabolic", "min": 40, "max": 500},
    {"key": "fasting_insulin", "label": "Fasting insulin", "unit": "µU/mL",
     "group": "Metabolic", "min": 0, "max": 200},
    {"key": "homa_ir", "label": "HOMA-IR", "unit": "unitless", "group": "Metabolic",
     "min": 0, "max": 50, "description": "Insulin resistance index."},
    {"key": "hdl", "label": "HDL cholesterol", "unit": "mg/dL", "group": "Lipids",
     "min": 10, "max": 150},
    {"key": "non_hdl_cholesterol", "label": "Non-HDL cholesterol", "unit": "mg/dL",
     "group": "Lipids", "min": 20, "max": 400},

    # Biological age outputs
    {"key": "phenoage", "label": "PhenoAge", "unit": "years",
     "group": "Biological age", "min": 0, "max": 120,
     "description": "Levine 2018 phenotypic biological age."},
    {"key": "phenoage_delta", "label": "PhenoAge delta", "unit": "years",
     "group": "Biological age", "min": -30, "max": 40,
     "description": "PhenoAge minus chronological age. Negative = biologically younger."},
    {"key": "kdm_bioage", "label": "KDM biological age", "unit": "years",
     "group": "Biological age", "min": 0, "max": 120,
     "description": "Klemera-Doubal/Belsky KDM biological age."},
    {"key": "kdm_advance", "label": "KDM advance", "unit": "years",
     "group": "Biological age", "min": -30, "max": 40,
     "description": "KDM biological age minus chronological age."},
]


def get_variable(key: str):
    """Return the variable dictionary entry for a given column key."""
    for v in VARIABLES:
        if v["key"] == key:
            return v
    return None


def numeric_filter_vars():
    """All variables with min/max — these become the cohort builder's numeric filters."""
    return [v for v in VARIABLES if "min" in v and "max" in v]


def categorical_filter_vars():
    """Categorical filter variables."""
    return [
        {"key": "sex", "label": "Sex", "options": SEX_LABELS},
        {"key": "race_ethnicity", "label": "Race / Ethnicity", "options": RACE_LABELS},
        {"key": "education", "label": "Education", "options": EDUCATION_LABELS},
    ]
