"""
Shared analytical primitives for INEXION hypothesis scripts.

Provides:
    assign_bands               -- 5-year age band x sex x BMI band assignment
    match_cohort_to_reference  -- 1:N nearest-cell matching to a reference cohort
    compute_ipw_weights        -- inverse-probability weighting against reference
    weighted_mean              -- safe weighted mean
    monte_carlo_ci             -- bootstrap CI for difference of means
    ascvd_pooled_cohort_2014   -- 10-year ASCVD risk per Goff et al. 2014
    bh_fdr                     -- Benjamini-Hochberg FDR correction
"""

from __future__ import annotations

import numpy as np
import pandas as pd

AGE_BAND_WIDTH = 5
BMI_BANDS = [(0, 25), (25, 30), (30, 35), (35, 100)]
MIN_MATCHED_REF_PER_CELL = 3
DEFAULT_MC_ITER = 10_000


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def assign_bands(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["age_band"] = (df["age"] // AGE_BAND_WIDTH).astype(int) * AGE_BAND_WIDTH
    df["bmi_band"] = pd.cut(
        df["bmi"],
        bins=[b[0] for b in BMI_BANDS] + [BMI_BANDS[-1][1]],
        right=False, labels=[f"{lo}-{hi}" for lo, hi in BMI_BANDS],
        include_lowest=True,
    ).astype(str)
    return df


def match_cohort_to_reference(
    cohort: pd.DataFrame, reference: pd.DataFrame, ratio: int = 4,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Sample matched reference patients on (age_band, sex, bmi_band)."""
    rng = rng or np.random.default_rng(20260520 + 10)
    cohort = assign_bands(cohort)
    reference = assign_bands(reference)
    matched = []
    for (ab, sx, bb), group in cohort.groupby(["age_band", "sex", "bmi_band"]):
        ref_pool = reference[
            (reference["age_band"] == ab) & (reference["sex"] == sx) & (reference["bmi_band"] == bb)
        ]
        n = min(len(group) * ratio, len(ref_pool))
        if n < MIN_MATCHED_REF_PER_CELL:
            continue
        sampled = ref_pool.sample(n=n, random_state=int(rng.integers(0, 2**31))).copy()
        sampled["matched_cell"] = f"{ab}|{sx}|{bb}"
        matched.append(sampled)
    return pd.concat(matched, ignore_index=True) if matched else pd.DataFrame()


# ---------------------------------------------------------------------------
# IPW lifestyle adjustment
# ---------------------------------------------------------------------------

def compute_ipw_weights(
    cohort: pd.DataFrame, reference: pd.DataFrame, covariates: list[str],
) -> pd.DataFrame:
    """Inverse-probability weighting against the reference covariate distribution."""
    cohort = cohort.copy()
    ref = reference.copy()
    for cov in covariates:
        if cov not in ref.columns or cov not in cohort.columns:
            continue
        if pd.api.types.is_numeric_dtype(ref[cov]):
            edges = np.unique(np.quantile(ref[cov].dropna(), np.linspace(0, 1, 11)))
            cohort[f"{cov}_bin"] = pd.cut(cohort[cov], bins=edges, include_lowest=True, labels=False)
            ref[f"{cov}_bin"] = pd.cut(ref[cov], bins=edges, include_lowest=True, labels=False)
        else:
            cohort[f"{cov}_bin"] = cohort[cov].astype("category").cat.codes
            ref[f"{cov}_bin"] = ref[cov].astype("category").cat.codes

    bin_cols = [f"{c}_bin" for c in covariates if f"{c}_bin" in cohort.columns]
    if not bin_cols:
        cohort["ipw_weight"] = 1.0
        return cohort

    ref_counts = ref.groupby(bin_cols).size().rename("n_ref")
    coh_counts = cohort.groupby(bin_cols).size().rename("n_coh")
    counts = pd.concat([ref_counts, coh_counts], axis=1).fillna(0)
    counts["p_ref"] = counts["n_ref"] / counts["n_ref"].sum()
    counts["p_coh"] = counts["n_coh"] / counts["n_coh"].sum()
    counts["ipw_weight"] = np.where(
        counts["p_coh"] > 0, counts["p_ref"] / counts["p_coh"], 0.0
    )
    weights = counts["ipw_weight"].reset_index()
    cohort = cohort.merge(weights, on=bin_cols, how="left")
    cohort["ipw_weight"] = cohort["ipw_weight"].fillna(0.0)
    cap = np.quantile(cohort["ipw_weight"], 0.99)
    cohort["ipw_weight"] = cohort["ipw_weight"].clip(upper=cap)
    return cohort


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def weighted_mean(values: np.ndarray, weights: np.ndarray | None = None) -> float:
    if weights is None or weights.sum() == 0:
        return float(np.mean(values))
    return float(np.average(values, weights=weights))


def monte_carlo_ci(
    cohort_deltas: np.ndarray, reference_deltas: np.ndarray,
    cohort_weights: np.ndarray | None = None, iterations: int = DEFAULT_MC_ITER,
    rng: np.random.Generator | None = None,
) -> dict:
    rng = rng or np.random.default_rng(20260520 + 11)
    diffs = np.empty(iterations)
    n_c, n_r = len(cohort_deltas), len(reference_deltas)
    for i in range(iterations):
        c_idx = rng.integers(0, n_c, n_c)
        r_idx = rng.integers(0, n_r, n_r)
        c_sample = cohort_deltas[c_idx]
        r_sample = reference_deltas[r_idx]
        if cohort_weights is not None:
            cw = cohort_weights[c_idx]
            diffs[i] = weighted_mean(c_sample, cw) - np.mean(r_sample)
        else:
            diffs[i] = np.mean(c_sample) - np.mean(r_sample)
    point = float(np.mean(diffs))
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    p_two_sided = float(2 * min(np.mean(diffs >= 0), np.mean(diffs <= 0)))
    return {
        "point_estimate": point, "ci_low": float(lo), "ci_high": float(hi),
        "p_value": p_two_sided, "iterations": iterations,
    }


def bh_fdr(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    """Benjamini-Hochberg FDR correction. Returns list of bools (significant or not)."""
    p_arr = np.asarray(p_values, dtype=float)
    n = len(p_arr)
    order = np.argsort(p_arr)
    ranked = p_arr[order]
    thresholds = (np.arange(1, n + 1) / n) * alpha
    pass_mask = ranked <= thresholds
    if pass_mask.any():
        k = np.max(np.where(pass_mask)[0])
        significant_idx = order[: k + 1]
    else:
        significant_idx = np.array([], dtype=int)
    result = [False] * n
    for i in significant_idx:
        result[i] = True
    return result


# ---------------------------------------------------------------------------
# ASCVD Pooled Cohort Equations (Goff et al. 2014, ACC/AHA)
# Estimates 10-year risk of hard ASCVD events in adults 40-79.
# Inputs in standard clinical units.
# ---------------------------------------------------------------------------

def _ascvd_score_row(
    sex: int, race_black: bool, age: float, total_chol: float, hdl: float,
    sbp: float, treated_bp: bool, diabetes: bool, smoker: bool,
) -> float | None:
    if not (40 <= age <= 79):
        return None
    ln_age = np.log(age)
    ln_chol = np.log(total_chol)
    ln_hdl = np.log(hdl)
    ln_sbp = np.log(sbp)
    smoker_i = 1 if smoker else 0
    diabetes_i = 1 if diabetes else 0
    treated_i = 1 if treated_bp else 0

    if sex == 2:  # Female
        if race_black:
            coef = (17.114*ln_age + 0.940*ln_chol + 0.0*ln_hdl + 27.820*ln_sbp*treated_i
                    + 6.087*ln_sbp*(1-treated_i) + 0.691*smoker_i + 0.874*diabetes_i)
            mean_coef = 86.61
            survival = 0.9533
        else:  # White / other
            coef = (-29.799*ln_age + 4.884*(ln_age**2) + 13.540*ln_chol - 3.114*ln_age*ln_chol
                    - 13.578*ln_hdl + 3.149*ln_age*ln_hdl + 2.019*ln_sbp*treated_i
                    + 1.957*ln_sbp*(1-treated_i) + 7.574*smoker_i - 1.665*ln_age*smoker_i
                    + 0.661*diabetes_i)
            mean_coef = -29.18
            survival = 0.9665
    else:  # Male
        if race_black:
            coef = (2.469*ln_age + 0.302*ln_chol + 0.0*ln_hdl + 1.916*ln_sbp*treated_i
                    + 1.809*ln_sbp*(1-treated_i) + 0.549*smoker_i + 0.645*diabetes_i)
            mean_coef = 19.54
            survival = 0.8954
        else:
            coef = (12.344*ln_age + 11.853*ln_chol - 2.664*ln_age*ln_chol
                    - 7.990*ln_hdl + 1.769*ln_age*ln_hdl + 1.797*ln_sbp*treated_i
                    + 1.764*ln_sbp*(1-treated_i) + 7.837*smoker_i - 1.795*ln_age*smoker_i
                    + 0.658*diabetes_i)
            mean_coef = 61.18
            survival = 0.9144

    risk = 1.0 - np.power(survival, np.exp(coef - mean_coef))
    return float(np.clip(risk, 0.0, 1.0))


def ascvd_pooled_cohort_2014(df: pd.DataFrame) -> pd.Series:
    """
    Compute 10-year ASCVD risk per row. Requires columns:
        age, sex (1=M, 2=F), total_cholesterol, hdl, systolic_mean,
        treated_bp (bool, default False), diabetes (bool, default False),
        smoker (bool, default False), race_black (bool, default False).
    Missing optional columns are treated as False.
    """
    df = df.copy()
    for c in ["treated_bp", "diabetes", "smoker", "race_black"]:
        if c not in df.columns:
            df[c] = False
    return df.apply(
        lambda r: _ascvd_score_row(
            int(r["sex"]) if pd.notna(r["sex"]) else 1,
            bool(r["race_black"]), float(r["age"]),
            float(r["total_cholesterol"]) if pd.notna(r["total_cholesterol"]) else np.nan,
            float(r["hdl"]) if pd.notna(r["hdl"]) else np.nan,
            float(r["systolic_mean"]) if pd.notna(r["systolic_mean"]) else np.nan,
            bool(r["treated_bp"]), bool(r["diabetes"]), bool(r["smoker"]),
        ) if pd.notna(r.get("total_cholesterol")) and pd.notna(r.get("hdl")) and pd.notna(r.get("systolic_mean"))
        else np.nan,
        axis=1,
    )
