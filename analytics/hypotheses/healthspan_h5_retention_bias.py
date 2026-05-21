"""
Healthspan H5 — Retention as a confounding signal.

Hypothesis: Patients who drop off Healthspan within 6 months are systematically
different at baseline from retained patients. Naive cohort analyses that exclude
drop-offs overstate the protocol effect by approximately 20-35%.

Pattern: Bronze read with retention flags -> compute ITT vs as-treated effects ->
quantify the bias magnitude. Defensibility-critical metric.
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

from analytics.lib.analysis import match_cohort_to_reference, monte_carlo_ci
from analytics.lib.manifest import (
    RunManifest, code_commit_hash, load_nhanes_reference, make_run_dir, write_run,
)
from analytics.lib.synth import generate_healthspan_cohort

HYPOTHESIS_ID = "HEALTHSPAN_H5"
HYPOTHESIS_TITLE = "Retention bias quantification"
log = logging.getLogger("HSH5")


def run(effect_size_years: float = -3.0):
    rng = np.random.default_rng(20260520)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== HSH5 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    cohort, used_idx = generate_healthspan_cohort(nhanes_all, effect_size_years=effect_size_years, rng=rng)
    reference_pool = nhanes_all.drop(index=used_idx).copy()
    matched_ref = match_cohort_to_reference(cohort, reference_pool, rng=rng)

    # ITT: all enrolled patients (including drop-offs)
    itt = monte_carlo_ci(
        cohort_deltas=cohort["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        rng=rng,
    )

    # As-treated: only retained patients
    as_treated_pool = cohort[cohort["retained_12mo"]]
    as_treated = monte_carlo_ci(
        cohort_deltas=as_treated_pool["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        rng=rng,
    )

    # Bias magnitude
    bias_yrs = as_treated["point_estimate"] - itt["point_estimate"]
    if itt["point_estimate"] != 0:
        bias_pct = 100.0 * bias_yrs / itt["point_estimate"]
    else:
        bias_pct = float("nan")

    # Baseline characteristics of dropoffs vs retained
    dropoffs = cohort[~cohort["retained_12mo"]]
    retained = cohort[cohort["retained_12mo"]]
    baseline_compare = {
        "n_dropoffs": int(len(dropoffs)),
        "n_retained": int(len(retained)),
        "retention_rate": float(len(retained) / len(cohort)),
        "mean_phenoage_delta_baseline_dropoffs": float(dropoffs["phenoage_delta"].mean()),
        "mean_phenoage_delta_baseline_retained": float(retained["phenoage_delta"].mean()),
        "mean_bmi_dropoffs": float(dropoffs["bmi"].mean()),
        "mean_bmi_retained": float(retained["bmi"].mean()),
        "pct_current_smokers_dropoffs": float(100 * (dropoffs["smoking_status"] == "current").mean()),
        "pct_current_smokers_retained": float(100 * (retained["smoking_status"] == "current").mean()),
    }

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_cohort_total": int(len(cohort)),
        "n_matched_reference": int(len(matched_ref)),
        "intention_to_treat": itt,
        "as_treated_retained_only": as_treated,
        "bias_magnitude_years": float(bias_yrs),
        "bias_magnitude_pct_of_itt": float(bias_pct) if bias_pct == bias_pct else None,
        "baseline_compare": baseline_compare,
        "interpretation": (
            "Negative bias_magnitude_years means the as-treated estimate is MORE negative "
            "(stronger apparent benefit) than ITT, indicating drop-off exclusion overstates "
            "the protocol effect. Hypothesis predicts 20-35% inflation."
        ),
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "n_cohort": int(len(cohort)),
            "n_matched_reference": int(len(matched_ref)),
            "itt_definition": "all enrolled patients including drop-offs",
            "as_treated_definition": "only patients retained at 12 months",
        },
        methods={
            "phenoage": "Levine 2018 (NHANES precomputed)",
            "matching": "5y age band x sex x BMI band, 4:1",
            "uncertainty": "Monte Carlo 10,000 iterations, 95% CI",
            "bias_metric": "(as_treated - itt) / itt",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_healthspan"],
        synthetic_data_flag=True,
        notes=[
            "Synthetic Healthspan cohort with simulated ~18% drop-off rate and systematic baseline differences.",
            "Production: replace with bronze_healthspan_* retention flag.",
        ],
    )
    write_run(output_dir, manifest, results, extras={"cohort": cohort, "matched_reference": matched_ref})
    log.info("==== HSH5 RUN COMPLETE: output=%s ====", output_dir)
    log.info("ITT Δ=%+.2f yrs | as-treated Δ=%+.2f yrs | bias=%+.2f yrs (%.1f%% of ITT)",
             itt["point_estimate"], as_treated["point_estimate"], bias_yrs, bias_pct)
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--effect-size", type=float, default=-3.0)
    args = parser.parse_args()
    run(effect_size_years=args.effect_size)
