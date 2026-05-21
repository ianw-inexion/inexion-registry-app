"""
Healthspan H1 — Cohort-level PhenoAge advantage vs NHANES reference.

Hypothesis (Healthspan / AgelessRx Engagement Hypotheses v3, HS H1):
    Healthspan patients with >= 12 months of protocol exposure show a PhenoAge delta
    (biological minus chronological age) that is 2 to 5 years more negative than an
    age- and sex-matched NHANES reference cohort, statistically significant at p<0.01.

This file is the worked example for the Bronze + analytics-script pattern specified in
INEXION Registry Schema v0.3. It demonstrates the full vertical slice:

    Bronze read  ->  cohort construction  ->  matched reference  ->  PhenoAge deltas
                                                     |
                                            IPW lifestyle adjustment
                                                     |
                                            Monte Carlo CI + BH FDR
                                                     |
                                       analysis_run manifest  +  HTML report

PRODUCTION USE
--------------
Two functions get replaced when real Healthspan data lands under DUA:
    load_healthspan_cohort(...)   -- swap stub for read of bronze_healthspan_*
    load_nhanes_reference(...)    -- already production; reads bronze_nhanes_*

The rest of the pipeline is unchanged. The script writes its results into
inex_analysis_run-compatible JSON for downstream reproducibility audit.

STAND-IN DATA
-------------
Until the Healthspan DUA executes, this script synthesizes a Healthspan-like cohort
from a slice of NHANES with a small simulated treatment-effect perturbation applied
to PhenoAge. Synthetic data is clearly tagged in the manifest. The numbers produced
are illustrative; the architecture and the report shape are real.

Author: INEXION analytics
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

# Resolve data paths via the existing app config. This works in three modes:
#   - local dev: INEXION_DATA_DIR unset, falls back to ../inexion-registry-pipeline/data/staging
#   - S3 dev:    INEXION_DATA_DIR=s3://inexion-registry/temp_Ian_Nirav/staging
#   - Streamlit Cloud: secrets auto-loaded into env vars by the app, picked up here
# Ensure the app root is on sys.path so 'src.config' imports correctly when the script
# is executed directly via `python analytics/hypotheses/healthspan_h1_phenoage_advantage.py`.
ANALYTICS_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ANALYTICS_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.config import NHANES_PARQUET, IS_S3, data_exists  # noqa: E402

TEMPLATES_DIR = ANALYTICS_DIR / "templates"
RUNS_DIR = ANALYTICS_DIR / "runs"

HYPOTHESIS_ID = "HEALTHSPAN_H1"
HYPOTHESIS_TITLE = "Cohort-level PhenoAge advantage"
PROTOCOL_VERSION = "v3"

# Matching grid: 5-year age band x sex x BMI band.
AGE_BAND_WIDTH = 5
BMI_BANDS = [(0, 25), (25, 30), (30, 35), (35, 100)]
MIN_MATCHED_REF_PER_CELL = 3  # below this, exclude the cell from primary estimate

# Lifestyle covariates for IPW adjustment (NHANES variables available today).
LIFESTYLE_COVARIATES = ["bmi"]  # extend with smoking, activity, alcohol when in Bronze

MC_ITERATIONS = 10_000
SEED = 20260520

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger("HSH1")


# --------------------------------------------------------------------------------------
# Run manifest (inex_analysis_run-compatible)
# --------------------------------------------------------------------------------------

@dataclass
class RunManifest:
    run_id: str
    hypothesis_id: str
    cohort_definition: dict
    methods: dict
    reference_cohort_version: str
    code_commit_hash: str
    ran_at: str
    output_uri: str
    data_partner_ids: list[str]
    synthetic_data_flag: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# --------------------------------------------------------------------------------------
# Bronze readers (swap-out points for production)
# --------------------------------------------------------------------------------------

def load_nhanes_reference() -> pd.DataFrame:
    """
    Production Bronze read for NHANES.

    Today: reads the harmonized NHANES parquet produced by inexion-registry-pipeline.
    When Bronze tables land in Postgres, this becomes a SQL query against bronze_nhanes_*.
    The column contract returned here is the public surface; downstream functions read
    only the columns named below.
    """
    if not data_exists(NHANES_PARQUET):
        raise FileNotFoundError(
            f"NHANES parquet not found at {NHANES_PARQUET}. "
            "Confirm INEXION_DATA_DIR is set (local path or s3://inexion-registry/...) "
            "and that the harmonized NHANES build has been published to that location."
        )
    cols = [
        "seqn", "cycle", "cycle_start_year",
        "age", "sex", "race_ethnicity", "bmi",
        "phenoage", "phenoage_delta",
        "exam_weight",
    ]
    con = duckdb.connect(database=":memory:")
    # DuckDB reads S3 paths directly when AWS credentials are set in the environment.
    # The httpfs extension is bundled in modern duckdb wheels; ensure it is loaded.
    if IS_S3:
        con.execute("INSTALL httpfs; LOAD httpfs;")
    path_str = str(NHANES_PARQUET) if IS_S3 else NHANES_PARQUET.as_posix()
    df = con.execute(
        f"SELECT {', '.join(cols)} FROM read_parquet('{path_str}') "
        f"WHERE phenoage IS NOT NULL AND age IS NOT NULL AND bmi IS NOT NULL "
        f"AND sex IS NOT NULL"
    ).df()
    df["source"] = "nhanes"
    log.info("Loaded NHANES reference from %s: n=%d", "S3" if IS_S3 else "local", len(df))
    return df


def load_healthspan_cohort(
    nhanes_pool: pd.DataFrame,
    effect_size_years: float = -3.0,
    n_cohort: int = 1_500,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """
    STAND-IN: synthesize a Healthspan-like cohort from NHANES with a simulated
    treatment-effect perturbation on PhenoAge. Tagged synthetic in the manifest.

    Production replacement:
        SELECT ... FROM bronze_healthspan_patients p
        JOIN bronze_healthspan_labs l ON l.person_id = p.person_id
        WHERE l.relative_day_protocol >= 365

    The signature stays the same: returns a DataFrame with the same column contract
    as load_nhanes_reference plus a treatment metadata column.
    """
    rng = rng or np.random.default_rng(SEED)

    # Healthspan demographic profile: ages 35-75, broad sex distribution, slight
    # skew toward overweight/obese (matches the cash-pay longevity patient archetype).
    eligible = nhanes_pool[
        (nhanes_pool["age"].between(35, 75))
        & (nhanes_pool["bmi"].between(20, 45))
    ].copy()

    if len(eligible) < n_cohort:
        n_cohort = len(eligible)
        log.warning("Reduced synthetic Healthspan cohort to n=%d (pool exhausted)", n_cohort)

    # Sample with a slight BMI-skewed weight to match the longevity archetype.
    weights = np.where(eligible["bmi"].values >= 27, 1.5, 1.0)
    weights = weights / weights.sum()
    idx = rng.choice(eligible.index.values, size=n_cohort, replace=False, p=weights)
    cohort = eligible.loc[idx].copy().reset_index(drop=True)

    # Apply the simulated treatment-effect perturbation to PhenoAge delta.
    # Centered at effect_size_years with SD of 1.5 years to simulate heterogeneity.
    perturbation = rng.normal(loc=effect_size_years, scale=1.5, size=len(cohort))
    cohort["phenoage"] = cohort["phenoage"] + perturbation
    cohort["phenoage_delta"] = cohort["phenoage"] - cohort["age"]

    cohort["source"] = "healthspan_synthetic"
    cohort["protocol_class"] = rng.choice(
        ["HRT", "GLP1", "NAD_PRECURSOR", "MULTI_MODAL", "PEPTIDES"],
        size=len(cohort),
        p=[0.30, 0.25, 0.15, 0.20, 0.10],
    )
    cohort["months_on_protocol"] = rng.integers(low=12, high=36, size=len(cohort))

    log.info(
        "Synthesized Healthspan-like cohort: n=%d, simulated PhenoAge delta perturbation %.1f years",
        len(cohort), effect_size_years,
    )
    return cohort, idx.tolist()


# --------------------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------------------

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
    cohort: pd.DataFrame,
    reference: pd.DataFrame,
    ratio: int = 4,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """
    For each cohort patient, sample up to `ratio` matched reference patients
    on (age_band, sex, bmi_band). Returns the matched reference subset with
    a matched_to column linking back to cohort seqn.
    """
    rng = rng or np.random.default_rng(SEED + 1)
    cohort = assign_bands(cohort)
    reference = assign_bands(reference)
    matched_rows = []
    cells_excluded = 0
    for (ab, sx, bb), group in cohort.groupby(["age_band", "sex", "bmi_band"]):
        ref_pool = reference[
            (reference["age_band"] == ab)
            & (reference["sex"] == sx)
            & (reference["bmi_band"] == bb)
        ]
        target_n = min(len(group) * ratio, len(ref_pool))
        if target_n < MIN_MATCHED_REF_PER_CELL:
            cells_excluded += 1
            continue
        sampled = ref_pool.sample(n=target_n, random_state=rng.integers(0, 2**31))
        sampled = sampled.copy()
        sampled["matched_cell"] = f"{ab}|{sx}|{bb}"
        matched_rows.append(sampled)
    out = pd.concat(matched_rows, ignore_index=True) if matched_rows else pd.DataFrame()
    log.info(
        "Matched reference: n=%d (target ratio %d:1, cells excluded for sparsity: %d)",
        len(out), ratio, cells_excluded,
    )
    return out


# --------------------------------------------------------------------------------------
# IPW lifestyle adjustment
# --------------------------------------------------------------------------------------

def compute_ipw_weights(
    cohort: pd.DataFrame,
    reference: pd.DataFrame,
    covariates: list[str],
) -> pd.DataFrame:
    """
    Inverse-probability weighting against the reference covariate distribution.
    Returns the cohort DataFrame with an `ipw_weight` column.

    Lightweight implementation suitable for Phase 1: estimates propensity of being
    in the cohort vs the reference via logistic-equivalent ratio of covariate-bin
    densities, then computes IPW = density_ref / density_cohort.
    """
    cohort = cohort.copy()
    ref = reference.copy()

    # Discretize each covariate into deciles of the reference distribution.
    for cov in covariates:
        edges = np.unique(np.quantile(ref[cov].dropna(), np.linspace(0, 1, 11)))
        cohort[f"{cov}_bin"] = pd.cut(cohort[cov], bins=edges, include_lowest=True, labels=False)
        ref[f"{cov}_bin"] = pd.cut(ref[cov], bins=edges, include_lowest=True, labels=False)

    bin_cols = [f"{c}_bin" for c in covariates]
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
    # Trim extreme weights at the 99th percentile to control variance.
    cap = np.quantile(cohort["ipw_weight"], 0.99)
    cohort["ipw_weight"] = cohort["ipw_weight"].clip(upper=cap)
    return cohort


# --------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------

def weighted_mean(values: np.ndarray, weights: np.ndarray | None = None) -> float:
    if weights is None or weights.sum() == 0:
        return float(np.mean(values))
    return float(np.average(values, weights=weights))


def monte_carlo_ci(
    cohort_deltas: np.ndarray,
    reference_deltas: np.ndarray,
    cohort_weights: np.ndarray | None = None,
    iterations: int = MC_ITERATIONS,
    rng: np.random.Generator | None = None,
) -> dict:
    rng = rng or np.random.default_rng(SEED + 2)
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
    # Two-sided p-value approximation against null mean 0.
    p_two_sided = float(2 * min(np.mean(diffs >= 0), np.mean(diffs <= 0)))
    return {
        "point_estimate": point,
        "ci_low": float(lo),
        "ci_high": float(hi),
        "p_value": p_two_sided,
        "iterations": iterations,
    }


# --------------------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------------------

def run_healthspan_h1(
    effect_size_years: float = -3.0,
    output_dir: Path | None = None,
) -> dict:
    rng = np.random.default_rng(SEED)
    run_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc).isoformat()

    log.info("==== HSH1 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    cohort, used_idx = load_healthspan_cohort(
        nhanes_all, effect_size_years=effect_size_years, rng=rng
    )
    # Reference cohort = remainder of NHANES (excluding the patients used to
    # synthesize the Healthspan cohort, to avoid double-counting in this stand-in).
    reference_pool = nhanes_all.drop(index=used_idx).copy()
    log.info("Reference pool (post-exclusion): n=%d", len(reference_pool))

    matched_ref = match_cohort_to_reference(cohort, reference_pool, ratio=4, rng=rng)
    cohort_w = compute_ipw_weights(cohort, matched_ref, LIFESTYLE_COVARIATES)

    unadjusted = monte_carlo_ci(
        cohort_deltas=cohort["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        rng=rng,
    )
    adjusted = monte_carlo_ci(
        cohort_deltas=cohort_w["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        cohort_weights=cohort_w["ipw_weight"].values,
        rng=rng,
    )

    # Stratified estimates by protocol class
    protocol_results = {}
    for protocol_class, group in cohort.groupby("protocol_class"):
        if len(group) < 30:
            continue
        protocol_results[str(protocol_class)] = {
            "n": int(len(group)),
            "mean_delta_cohort": float(group["phenoage_delta"].mean()),
        }

    output_dir = output_dir or RUNS_DIR / f"HSH1_{started_at[:10]}_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest(
        run_id=run_id,
        hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "cohort_source": "synthetic_healthspan_from_nhanes",
            "n_cohort": int(len(cohort)),
            "age_range": [35, 75],
            "bmi_range": [20, 45],
            "min_months_on_protocol": 12,
            "matched_reference_source": "nhanes_pool_excluding_cohort_patients",
            "n_matched_reference": int(len(matched_ref)),
            "match_strategy": "age_band_5y x sex x bmi_band",
            "match_ratio": 4,
        },
        methods={
            "phenoage_implementation": "Levine 2018 (NHANES precomputed)",
            "ipw_covariates": LIFESTYLE_COVARIATES,
            "uncertainty": f"Monte Carlo {MC_ITERATIONS} iterations, 95% CI",
            "multiple_comparison_correction": "BH FDR at 0.05 (n.a. for single-hypothesis run)",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=os.environ.get("GIT_COMMIT", "uncommitted"),
        ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_healthspan"],
        synthetic_data_flag=True,
        notes=[
            f"Synthetic Healthspan cohort: effect_size_years={effect_size_years}, scale=1.5.",
            "Production: replace load_healthspan_cohort() with bronze_healthspan_* read.",
        ],
    )

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_cohort": int(len(cohort)),
        "n_matched_reference": int(len(matched_ref)),
        "unadjusted_delta_difference": unadjusted,
        "lifestyle_adjusted_delta_difference": adjusted,
        "by_protocol_class": protocol_results,
        "mean_phenoage_delta_cohort": float(cohort["phenoage_delta"].mean()),
        "mean_phenoage_delta_reference_matched": float(matched_ref["phenoage_delta"].mean()),
    }

    out_manifest_path = output_dir / "manifest.json"
    out_results_path = output_dir / "results.json"
    out_cohort_path = output_dir / "cohort.parquet"
    out_matched_path = output_dir / "matched_reference.parquet"
    out_manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))
    out_results_path.write_text(json.dumps(results, indent=2, default=str))
    cohort.to_parquet(out_cohort_path, index=False)
    matched_ref.to_parquet(out_matched_path, index=False)

    # Generate report
    try:
        from analytics.templates.report import render_report  # type: ignore
        report_html = render_report(manifest.to_dict(), results)
        (output_dir / "report.html").write_text(report_html)
    except Exception as e:
        log.warning("Report rendering skipped: %s", e)

    log.info("==== HSH1 RUN COMPLETE: output_dir=%s ====", output_dir)
    log.info("Headline: unadjusted Δ = %+0.2f yrs [%+0.2f, %+0.2f], p=%.4f",
             unadjusted["point_estimate"], unadjusted["ci_low"], unadjusted["ci_high"],
             unadjusted["p_value"])
    log.info("Headline: IPW-adjusted Δ = %+0.2f yrs [%+0.2f, %+0.2f], p=%.4f",
             adjusted["point_estimate"], adjusted["ci_low"], adjusted["ci_high"],
             adjusted["p_value"])
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Healthspan H1 PhenoAge advantage analysis.")
    parser.add_argument("--effect-size", type=float, default=-3.0,
                        help="Simulated treatment effect for the synthetic cohort (years).")
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()
    run_healthspan_h1(
        effect_size_years=args.effect_size,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
       adjusted["point_estimate"], adjusted["ci_low"], adjusted["ci_high"],
             adjusted["p_value"])
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Healthspan H1 PhenoAge advantage analysis.")
    parser.add_argument("--effect-size", type=float, default=-3.0,
                        help="Simulated treatment effect for the synthetic cohort (years).")
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()
    run_healthspan_h1(
        effect_size_years=args.effect_size,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
