"""
Self-contained PhenoAge + KDM biological age computation for the calculator page.

Mirrors the coefficients and formulas in
inexion-registry-pipeline/inexion_registry/bioage/phenoage.py — kept here so
the app runs without importing the pipeline package.
"""
from __future__ import annotations
import math
from typing import Optional

# PhenoAge — Levine 2018 / BioAge R package (Kwon & Belsky)
PHENOAGE_COEFFS = {
    "albumin":              -0.03359355,   # per g/L (SI; mg/dL × 10)
    "creatinine":            0.009506491,  # per µmol/L (mg/dL × 88.4)
    "glucose_biopro":        0.1953192,    # per mmol/L (mg/dL ÷ 18.02)
    "ln_crp":                0.09536762,   # per ln(mg/L)
    "lymphocyte_pct":       -0.01199984,   # per %
    "mcv":                   0.02676401,   # per fL
    "rdw":                   0.3306156,    # per %
    "alkaline_phosphatase":  0.001868778,  # per U/L
    "wbc":                   0.05542406,   # per 1000/µL
    "age":                   0.08035356,   # per year
}
PHENOAGE_INTERCEPT = -19.90667
GOMPERTZ_GAMMA = -1.51714
GOMPERTZ_DIVISOR = 0.007692696
PHENOAGE_CONSTANT = 141.50225
PHENOAGE_MORT_COEFF = -0.0055305
PHENOAGE_AGE_DIVISOR = 0.090165


def compute_phenoage(
    age: float,
    albumin_g_dl: float,
    creatinine_mg_dl: float,
    glucose_mg_dl: float,
    crp_mg_l: float,
    lymphocyte_pct: float,
    mcv_fl: float,
    rdw_pct: float,
    alk_phos_u_l: float,
    wbc_1000_ul: float,
) -> dict[str, float]:
    """
    Compute PhenoAge from 9 clinical biomarkers + age, in NHANES native units.
    Returns {phenoage, delta, mortality_10y}.
    """
    # Unit conversions to SI where required
    albumin_si = albumin_g_dl * 10.0
    creatinine_si = creatinine_mg_dl * 88.4
    glucose_si = glucose_mg_dl / 18.02
    ln_crp = math.log(max(crp_mg_l, 0.01))

    xb = (
        PHENOAGE_INTERCEPT
        + PHENOAGE_COEFFS["albumin"]              * albumin_si
        + PHENOAGE_COEFFS["creatinine"]           * creatinine_si
        + PHENOAGE_COEFFS["glucose_biopro"]       * glucose_si
        + PHENOAGE_COEFFS["ln_crp"]               * ln_crp
        + PHENOAGE_COEFFS["lymphocyte_pct"]       * lymphocyte_pct
        + PHENOAGE_COEFFS["mcv"]                  * mcv_fl
        + PHENOAGE_COEFFS["rdw"]                  * rdw_pct
        + PHENOAGE_COEFFS["alkaline_phosphatase"] * alk_phos_u_l
        + PHENOAGE_COEFFS["wbc"]                  * wbc_1000_ul
        + PHENOAGE_COEFFS["age"]                  * age
    )

    # 10-year mortality probability
    m = 1.0 - math.exp((GOMPERTZ_GAMMA * math.exp(xb)) / GOMPERTZ_DIVISOR)
    m = min(max(m, 1e-10), 1 - 1e-10)

    phenoage = (
        math.log(PHENOAGE_MORT_COEFF * math.log(1 - m)) / PHENOAGE_AGE_DIVISOR
        + PHENOAGE_CONSTANT
    )
    return {
        "phenoage": phenoage,
        "delta": phenoage - age,
        "mortality_10y": m,
    }
