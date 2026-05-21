"""
Healthspan H4 — Lifestyle-adjusted protocol attribution.

Hypothesis: After lifestyle adjustment (BMI, smoking, activity), at least 60% of
the raw PhenoAge delta remains attributable to protocol exposure. The protocol-
specific effect is larger in patients with adverse baseline lifestyle than in
patients with favorable baseline lifestyle.

Pattern: Bronze read -> matched reference -> compute unadjusted delta -> apply
IPW with lifestyle covariates -> compute adjusted delta -> report retention ratio.
"""

from __future__ import annotations

import argparse
import logging

import numpy as np

import sys as _sys
from pathlib import Path as _Path
_APP_DIR = _Path(__file__).resolve().parents[2]
if str(_APP_DIR) not in _sys.path:
    _sys.path.insert(0, str(_APP_DIR))

from analytics.lib.analysis import (
    compute_ipw_weights, match_cohort_to_reference, monte_carlo_ci,
)
from analytics.lib.manifest import (
    RunManifest, code_commit_hash, load_nhanes_reference, make_run_dir, write_run,
)
from analytics.lib.synth import generate_healthspan_cohort

HYPOTHESIS_ID = "HEALTHSPAN_H4"
HYPOTHESIS_TITLE = "Lifestyle-adjusted PhenoAge attribution"
LIFESTYLE_COVARIATES = ["bmi", "smoking_status", "activity_level"]
log = logging.getLogger("HSH4")


def run(effect_size_years: float = -3.0):
    rng = np.random.default_rng(20260520)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== HSH4 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    cohort, used_idx = generate_healthspan_cohort(nhanes_all, effect_size_years=effect_size_years, rng=rng)
    reference_pool = nhanes_all.drop(index=used_idx).copy()
    # Reference cohort needs the lifestyle covariates too — synthesize matching distributions
    rng_ref = np.random.default_rng(20260520 + 50)
    reference_pool["smoking_status"] = rng_ref.choice(
        ["never", "former", "current"], size=len(reference_pool), p=[0.45, 0.30, 0.25],
    )
    reference_pool["activity_level"] = rng_ref.choice(
        ["low", "moderate", "high"], size=len(reference_pool), p=[0.45, 0.40, 0.15],
    )
    matched_ref = match_cohort_to_reference(cohort, reference_pool, rng=rng)

    unadjusted = monte_carlo_ci(
        cohort_deltas=cohort["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        rng=rng,
    )

    cohort_w = compute_ipw_weights(cohort, matched_ref, LIFESTYLE_COVARIATES)
    adjusted = monte_carlo_ci(
        cohort_deltas=cohort_w["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        cohort_weights=cohort_w["ipw_weight"].values,
        rng=rng,
    )

    if unadjusted["point_estimate"] != 0:
        attribution_retained = adjusted["point_estimate"] / unadjusted["point_estimate"]
    else:
        attribution_retained = float("nan")

    # Heterogeneity: split cohort by baseline lifestyle favorability
    cohort_w["unfavorable_lifestyle"] = (
        (cohort_w["smoking_status"] == "current") | (cohort_w["activity_level"] == "low")
    )
    by_lifestyle = {}
    for is_unfav, group in cohort_w.groupby("unfavorable_lifestyle"):
        if len(group) < 50:
            continue
        ci = monte_carlo_ci(
            cohort_deltas=group["phenoage_delta"].values,
            reference_deltas=matched_ref["phenoage_delta"].values,
            cohort_weights=group["ipw_weight"].values,
            rng=rng,
        )
        by_lifestyle["unfavorable_baseline" if is_unfav else "favorable_baseline"] = {
            "n": int(len(group)), **ci,
        }

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_cohort": int(len(cohort)),
        "n_matched_reference": int(len(matched_ref)),
        "unadjusted_delta_difference": unadjusted,
        "lifestyle_adjusted_delta_difference": adjusted,
        "attribution_retained_fraction": float(attribution_retained) if attribution_retained == attribution_retained else None,
        "by_baseline_lifestyle": by_lifestyle,
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "n_cohort": int(len(cohort)),
            "n_matched_reference": int(len(matched_ref)),
            "matching": "5y age band x sex x BMI band, 4:1",
        },
        methods={
            "phenoage": "Levine 2018 (NHANES precomputed)",
            "ipw_covariates": LIFESTYLE_COVARIATES,
            "uncertainty": "Monte Carlo 10,000 iterations, 95% CI",
            "heterogeneity": "stratify by unfavorable baseline lifestyle (current smoking OR low activity)",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_healthspan"],
        synthetic_data_flag=True,
        notes=[
            f"Synthetic Healthspan cohort with simulated -{abs(effect_size_years)} yr baseline effect.",
            "Lifestyle covariates synthesized at cohort and reference level.",
        ],
    )
    write_run(output_dir, manifest, results, extras={"cohort": cohort_w, "matched_reference": matched_ref})
    log.info("==== HSH4 RUN COMPLETE: output=%s ====", output_dir)
    log.info("Unadj Δ=%+.2f yrs | IPW-adj Δ=%+.2f yrs | retained=%.0f%%",
             unadjusted["point_estimate"], adjusted["point_estimate"],
             100 * attribution_retained if attribution_retained == attribution_retained else float("nan"))
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--effect-size", type=float, default=-3.0)
    args = parser.parse_args()
    run(effect_size_years=args.effect_size)
