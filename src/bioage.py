"""
Self-contained PhenoAge + KDM biological age computation for the calculator page.
Mirrors the coefficients and formulas in inexion-registry-pipeline.
"""
from __future__ import annotations
import math
from typing import Optional
import numpy as np


# Typical analytical (within-lab) coefficients of variation for the 9 PhenoAge
# inputs. Sources: CAP / CLIA proficiency-testing tolerance ranges; conservative
# midpoints when ranges vary.
PHENOAGE_INPUT_CV = {
    "albumin":         0.025,
    "creatinine":      0.030,
    "glucose":         0.025,
    "crp":             0.080,
    "lymphocyte_pct":  0.050,
    "mcv":             0.015,
    "rdw":             0.020,
    "alk_phos":        0.040,
    "wbc":             0.040,
}

PHENOAGE_COEFFS = {
    "albumin":              -0.03359355,
    "creatinine":            0.009506491,
    "glucose_biopro":        0.1953192,
    "ln_crp":                0.09536762,
    "lymphocyte_pct":       -0.01199984,
    "mcv":                   0.02676401,
    "rdw":                   0.3306156,
    "alkaline_phosphatase":  0.001868778,
    "wbc":                   0.05542406,
    "age":                   0.08035356,
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
) -> dict:
    """
    Compute PhenoAge from 9 clinical biomarkers + age, in NHANES native units.
    Returns {phenoage, delta, mortality_10y}.
    """
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


def bootstrap_phenoage(
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
    n_boot: int = 1000,
    seed: int = 42,
) -> dict:
    """
    Monte Carlo propagation of analytical measurement error through PhenoAge.

    Each of the 9 biomarker inputs is perturbed independently on every draw.
    Linear-scale inputs use Normal(value, value * CV); CRP uses log-Normal.
    Age is treated as exact. Returns the median plus the 2.5/97.5 percentile
    interval over `n_boot` draws.

    The resulting CI represents "if I drew this patient's blood again under
    identical lab conditions, where would PhenoAge land 95% of the time?"
    It is *not* a population CI - it captures within-patient analytical
    noise only, not between-person variation or model uncertainty.
    """
    rng = np.random.default_rng(seed)
    cv = PHENOAGE_INPUT_CV
    pa_draws = np.empty(n_boot, dtype=float)
    delta_draws = np.empty(n_boot, dtype=float)
    mort_draws = np.empty(n_boot, dtype=float)

    log_crp = math.log(max(crp_mg_l, 0.01))
    log_crp_sigma = cv["crp"]

    for i in range(n_boot):
        b_alb = albumin_g_dl     * (1 + rng.normal(0, cv["albumin"]))
        b_cre = creatinine_mg_dl * (1 + rng.normal(0, cv["creatinine"]))
        b_glu = glucose_mg_dl    * (1 + rng.normal(0, cv["glucose"]))
        b_crp = math.exp(log_crp + rng.normal(0, log_crp_sigma))
        b_lym = lymphocyte_pct   * (1 + rng.normal(0, cv["lymphocyte_pct"]))
        b_mcv = mcv_fl           * (1 + rng.normal(0, cv["mcv"]))
        b_rdw = rdw_pct          * (1 + rng.normal(0, cv["rdw"]))
        b_alk = alk_phos_u_l     * (1 + rng.normal(0, cv["alk_phos"]))
        b_wbc = wbc_1000_ul      * (1 + rng.normal(0, cv["wbc"]))

        out = compute_phenoage(
            age, b_alb, b_cre, b_glu, b_crp, b_lym,
            b_mcv, b_rdw, b_alk, b_wbc,
        )
        pa_draws[i] = out["phenoage"]
        delta_draws[i] = out["delta"]
        mort_draws[i] = out["mortality_10y"]

    return {
        "phenoage_p50": float(np.percentile(pa_draws, 50)),
        "phenoage_lo":  float(np.percentile(pa_draws, 2.5)),
        "phenoage_hi":  float(np.percentile(pa_draws, 97.5)),
        "delta_p50":    float(np.percentile(delta_draws, 50)),
        "delta_lo":     float(np.percentile(delta_draws, 2.5)),
        "delta_hi":     float(np.percentile(delta_draws, 97.5)),
        "mort_p50":     float(np.percentile(mort_draws, 50)),
        "mort_lo":      float(np.percentile(mort_draws, 2.5)),
        "mort_hi":      float(np.percentile(mort_draws, 97.5)),
        "n_boot":       int(n_boot),
    }
