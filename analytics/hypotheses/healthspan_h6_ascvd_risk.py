"""
Healthspan H6 — Projected ASCVD risk reduction.

Hypothesis: Healthspan patients aged 50+ on cardiometabolic-active protocols
(HRT, GLP-1, or combined) show a projected 10-year ASCVD risk (Pooled Cohort
Equations, Goff 2014) that is 15-30% lower at 12-month follow-up than baseline-
matched NHANES participants over the same horizon.

Pattern: Bronze read -> filter to age 50+ on cardiometabolic protocols -> compute
ASCVD per patient -> matched NHANES reference -> percent risk reduction with MC CI.
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

from analytics.lib.analysis import ascvd_pooled_cohort_2014, match_cohort_to_reference, monte_carlo_ci
from analytics.lib.manifest import (
    RunManifest, code_commit_hash, load_nhanes_reference, make_run_dir, write_run,
)
from analytics.lib.synth import generate_healthspan_cohort

HYPOTHESIS_ID = "HEALTHSPAN_H6"
HYPOTHESIS_TITLE = "Projected 10-year ASCVD risk reduction"
CARDIOMETABOLIC_CLASSES = {"HRT", "GLP1", "MULTI_MODAL"}
log = logging.getLogger("HSH6")


def run(effect_size_years: float = -3.0):
    rng = np.random.default_rng(20260520)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== HSH6 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    cohort_full, used_idx = generate_healthspan_cohort(nhanes_all, effect_size_years=effect_size_years, rng=rng)

    # Restrict to age 50+ on cardiometabolic protocols
    cohort = cohort_full[
        (cohort_full["age"] >= 50)
        & (cohort_full["protocol_class"].isin(CARDIOMETABOLIC_CLASSES))
    ].copy()

    if len(cohort) < 100:
        log.warning("Cardiometabolic 50+ subcohort too small (n=%d). Producing partial result.", len(cohort))

    age50_pool = nhanes_all[nhanes_all["age"] >= 50]
    reference_pool = age50_pool.drop(index=[i for i in used_idx if i in age50_pool.index])
    matched_ref = match_cohort_to_reference(cohort, reference_pool, rng=rng)

    # Simulate a treatment effect on ASCVD inputs in the cohort (lower SBP, higher HDL, lower chol)
    # mirrors the published cardiometabolic-improvement signature of these classes
    cohort["systolic_mean"] = cohort["systolic_mean"] - rng.normal(8.0, 3.0, len(cohort))
    cohort["hdl"] = cohort["hdl"] + rng.normal(4.0, 2.0, len(cohort))
    cohort["total_cholesterol"] = cohort["total_cholesterol"] - rng.normal(12.0, 5.0, len(cohort))
    cohort["smoker"] = (cohort["smoking_status"] == "current") if "smoking_status" in cohort.columns else False
    matched_ref["smoker"] = False  # NHANES doesn't carry our synthesized smoking flag through matching

    cohort["ascvd_10yr_risk"] = ascvd_pooled_cohort_2014(cohort)
    matched_ref["ascvd_10yr_risk"] = ascvd_pooled_cohort_2014(matched_ref)

    cohort_ascvd = cohort["ascvd_10yr_risk"].dropna().values
    ref_ascvd = matched_ref["ascvd_10yr_risk"].dropna().values

    # Difference of means CI (cohort - reference). Negative = lower risk in cohort.
    abs_ci = monte_carlo_ci(cohort_deltas=cohort_ascvd, reference_deltas=ref_ascvd, rng=rng)

    # Relative reduction percentage
    cohort_mean = float(np.mean(cohort_ascvd))
    ref_mean = float(np.mean(ref_ascvd))
    relative_reduction_pct = 100.0 * (ref_mean - cohort_mean) / ref_mean if ref_mean > 0 else float("nan")

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_cohort_cardiometabolic_50plus": int(len(cohort)),
        "n_matched_reference": int(len(matched_ref)),
        "mean_ascvd_10yr_risk_cohort": cohort_mean,
        "mean_ascvd_10yr_risk_reference": ref_mean,
        "absolute_risk_difference": abs_ci,
        "relative_risk_reduction_pct": float(relative_reduction_pct),
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "n_cohort_cardiometabolic_50plus": int(len(cohort)),
            "n_matched_reference": int(len(matched_ref)),
            "cardiometabolic_classes": sorted(CARDIOMETABOLIC_CLASSES),
            "age_floor": 50,
        },
        methods={
            "ascvd_equation": "Pooled Cohort Equations (Goff et al. 2014, ACC/AHA)",
            "matching": "5y age band x sex x BMI band, 4:1",
            "uncertainty": "Monte Carlo 10,000 iterations, 95% CI",
            "simulated_protocol_effect_on_ascvd_inputs": "SBP -8 mmHg, HDL +4 mg/dL, TC -12 mg/dL (synthetic)",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_healthspan"],
        synthetic_data_flag=True,
        notes=[
            "Synthetic Healthspan 50+ cardiometabolic subcohort with simulated treatment effects on BP, HDL, TC.",
            "Production: bronze_healthspan_labs read at 12-month follow-up, no simulated perturbations.",
        ],
    )
    write_run(output_dir, manifest, results, extras={"cohort": cohort, "matched_reference": matched_ref})
    log.info("==== HSH6 RUN COMPLETE: output=%s ====", output_dir)
    log.info("Mean ASCVD risk: cohort=%.3f, ref=%.3f | relative reduction=%.1f%%",
             cohort_mean, ref_mean, relative_reduction_pct)
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--effect-size", type=float, default=-3.0)
    args = parser.parse_args()
    run(effect_size_years=args.effect_size)
