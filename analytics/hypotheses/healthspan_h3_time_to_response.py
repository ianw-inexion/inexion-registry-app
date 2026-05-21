"""
Healthspan H3 — Time-to-response.

Hypothesis: Biomarker improvement is detectable within 3-6 months of protocol
initiation. PhenoAge delta stabilizes between 12 and 18 months and does not show
further meaningful improvement at 24 months.

Pattern: Bronze read -> longitudinal synthesis (4 timepoints per patient) ->
within-patient PhenoAge delta trajectory -> month-level summary -> plateau detection.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

import sys as _sys
from pathlib import Path as _Path
_APP_DIR = _Path(__file__).resolve().parents[2]
if str(_APP_DIR) not in _sys.path:
    _sys.path.insert(0, str(_APP_DIR))

from analytics.lib.manifest import (
    RunManifest, code_commit_hash, load_nhanes_reference, make_run_dir, write_run,
)
from analytics.lib.synth import generate_healthspan_cohort, generate_longitudinal_timepoints

HYPOTHESIS_ID = "HEALTHSPAN_H3"
HYPOTHESIS_TITLE = "Time-to-response trajectory"
log = logging.getLogger("HSH3")


def run(effect_size_years: float = -3.0):
    rng = np.random.default_rng(20260520)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== HSH3 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    baseline, used_idx = generate_healthspan_cohort(nhanes_all, effect_size_years=effect_size_years, rng=rng)
    longitudinal = generate_longitudinal_timepoints(
        baseline, n_timepoints=5, months_between=6, response_trajectory="exponential_plateau", rng=rng,
    )

    # Per-timepoint summary
    summary = (
        longitudinal.groupby("timepoint_month")
        .agg(
            n=("phenoage_delta", "count"),
            mean_delta=("phenoage_delta", "mean"),
            std_delta=("phenoage_delta", "std"),
            median_delta=("phenoage_delta", "median"),
        )
        .reset_index()
    )

    # Plateau detection: define plateau as where successive improvements drop below 0.25 yr
    summary["delta_to_previous"] = summary["mean_delta"].diff()
    plateau_month = None
    for _, row in summary.iterrows():
        if row["timepoint_month"] >= 12 and pd.notna(row["delta_to_previous"]) and abs(row["delta_to_previous"]) < 0.25:
            plateau_month = int(row["timepoint_month"])
            break

    # Detect time-to-detectable improvement (first month where mean delta < -0.5 vs baseline)
    baseline_mean = summary.loc[summary["timepoint_month"] == 0, "mean_delta"].iloc[0]
    detectable_month = None
    for _, row in summary.iterrows():
        if row["timepoint_month"] > 0 and (row["mean_delta"] - baseline_mean) < -0.5:
            detectable_month = int(row["timepoint_month"])
            break

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_cohort_baseline": int(len(baseline)),
        "n_timepoints": int(summary.shape[0]),
        "time_to_detectable_improvement_months": detectable_month,
        "plateau_month": plateau_month,
        "trajectory": summary.to_dict(orient="records"),
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "n_cohort": int(len(baseline)),
            "n_timepoints_per_patient": 5,
            "months_between_timepoints": 6,
            "longitudinal_model": "exponential_plateau (synthetic)",
        },
        methods={
            "phenoage": "Levine 2018 (NHANES precomputed)",
            "trajectory": "within-patient longitudinal change over 5 timepoints",
            "plateau_definition": "first month >=12 with absolute change <0.25 yr from prior",
            "detectable_definition": "first month where mean delta improves >=0.5 yr from baseline",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_healthspan"],
        synthetic_data_flag=True,
        notes=[
            "Synthetic longitudinal cohort. Production: replace with bronze_healthspan_labs longitudinal join.",
        ],
    )
    write_run(output_dir, manifest, results, extras={"longitudinal": longitudinal, "summary": summary})
    log.info("==== HSH3 RUN COMPLETE: output=%s ====", output_dir)
    log.info("Detectable improvement month: %s | Plateau month: %s", detectable_month, plateau_month)
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--effect-size", type=float, default=-3.0)
    args = parser.parse_args()
    run(effect_size_years=args.effect_size)
