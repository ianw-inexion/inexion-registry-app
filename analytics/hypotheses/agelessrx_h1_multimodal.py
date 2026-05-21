"""
AgelessRx H1 — Multi-modal protocol cohort PhenoAge advantage.

Hypothesis: AgelessRx patients on three or more concurrent active protocols
show a PhenoAge delta that is 3-6 years more negative than matched NHANES
controls at 12 months — a larger effect than any single-protocol arm.

Pattern: Bronze read -> partition by concurrent_protocol_count -> matched
NHANES reference -> per-arm MC CI -> direct comparison multi-modal vs single-arm.
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
from analytics.lib.synth import generate_agelessrx_cohort

HYPOTHESIS_ID = "AGELESSRX_H1"
HYPOTHESIS_TITLE = "Multi-modal protocol PhenoAge advantage"
MULTIMODAL_THRESHOLD = 3
log = logging.getLogger("ARXH1")


def run():
    rng = np.random.default_rng(20260520 + 1)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== ARXH1 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    cohort, used_idx = generate_agelessrx_cohort(nhanes_all, rng=rng)
    reference_pool = nhanes_all.drop(index=used_idx)
    matched_ref = match_cohort_to_reference(cohort, reference_pool, rng=rng)

    multimodal = cohort[cohort["concurrent_protocol_count"] >= MULTIMODAL_THRESHOLD]
    single_arm = cohort[cohort["concurrent_protocol_count"] < MULTIMODAL_THRESHOLD]

    mm_ci = monte_carlo_ci(
        cohort_deltas=multimodal["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        rng=rng,
    )
    sa_ci = monte_carlo_ci(
        cohort_deltas=single_arm["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        rng=rng,
    )

    # Direct comparison multi-modal vs single-arm
    direct_ci = monte_carlo_ci(
        cohort_deltas=multimodal["phenoage_delta"].values,
        reference_deltas=single_arm["phenoage_delta"].values,
        rng=rng,
    )

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_cohort_total": int(len(cohort)),
        "n_multimodal": int(len(multimodal)),
        "n_single_arm": int(len(single_arm)),
        "n_matched_reference": int(len(matched_ref)),
        "multimodal_vs_nhanes_delta_difference": mm_ci,
        "single_arm_vs_nhanes_delta_difference": sa_ci,
        "multimodal_vs_single_arm_delta_difference": direct_ci,
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "n_cohort": int(len(cohort)),
            "n_multimodal": int(len(multimodal)),
            "n_single_arm": int(len(single_arm)),
            "multimodal_definition": f"concurrent_protocol_count >= {MULTIMODAL_THRESHOLD}",
        },
        methods={
            "phenoage": "Levine 2018 (NHANES precomputed)",
            "matching": "5y age band x sex x BMI band, 4:1",
            "uncertainty": "Monte Carlo 10,000 iterations, 95% CI",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_agelessrx"],
        synthetic_data_flag=True,
        notes=[
            "Synthetic AgelessRx cohort with multi-modal vs single-arm partitioning.",
            "Production: replace generate_agelessrx_cohort with bronze_agelessrx_* read.",
        ],
    )
    write_run(output_dir, manifest, results, extras={"cohort": cohort, "matched_reference": matched_ref})
    log.info("==== ARXH1 RUN COMPLETE: output=%s ====", output_dir)
    log.info("Multi-modal Δ=%+.2f, single-arm Δ=%+.2f, direct comparison=%+.2f",
             mm_ci["point_estimate"], sa_ci["point_estimate"], direct_ci["point_estimate"])
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    run()
