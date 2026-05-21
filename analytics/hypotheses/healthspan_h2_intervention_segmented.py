"""
Healthspan H2 — Intervention-segmented response.

Hypothesis: PhenoAge delta differs materially across Healthspan's three highest-volume
intervention classes. HRT shows the largest improvement; GLP-1 monotherapy shows the
largest cardiometabolic-biomarker movement; NAD+ precursors alone show the smallest
measurable effect at 12 months.

Pattern: Bronze read -> protocol-class subgroup analysis -> within-cohort
comparison + matched NHANES reference -> per-class Monte Carlo CI -> BH FDR
across the multi-class family.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

import sys as _sys
from pathlib import Path as _Path
_APP_DIR = _Path(__file__).resolve().parents[2]
if str(_APP_DIR) not in _sys.path:
    _sys.path.insert(0, str(_APP_DIR))

from analytics.lib.analysis import (
    match_cohort_to_reference, monte_carlo_ci, bh_fdr,
)
from analytics.lib.manifest import (
    RunManifest, code_commit_hash, load_nhanes_reference, make_run_dir, write_run,
)
from analytics.lib.synth import generate_healthspan_cohort

HYPOTHESIS_ID = "HEALTHSPAN_H2"
HYPOTHESIS_TITLE = "Intervention-segmented PhenoAge response"
MIN_N_PER_CLASS = 100
log = logging.getLogger("HSH2")


def run(effect_size_years: float = -3.0):
    rng = np.random.default_rng(20260520)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== HSH2 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    cohort, used_idx = generate_healthspan_cohort(nhanes_all, effect_size_years=effect_size_years, rng=rng)
    reference_pool = nhanes_all.drop(index=used_idx)
    matched_ref = match_cohort_to_reference(cohort, reference_pool, rng=rng)

    by_class = {}
    raw_pvals = []
    class_names = []
    for cls, group in cohort.groupby("protocol_class"):
        if len(group) < MIN_N_PER_CLASS:
            by_class[cls] = {"n": int(len(group)), "skipped": "below MIN_N_PER_CLASS"}
            continue
        ci = monte_carlo_ci(
            cohort_deltas=group["phenoage_delta"].values,
            reference_deltas=matched_ref["phenoage_delta"].values,
            rng=rng,
        )
        by_class[cls] = {"n": int(len(group)), **ci}
        raw_pvals.append(ci["p_value"])
        class_names.append(cls)

    sig_mask = bh_fdr(raw_pvals, alpha=0.05)
    for name, sig in zip(class_names, sig_mask):
        by_class[name]["significant_after_bh_fdr"] = bool(sig)

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_cohort": int(len(cohort)),
        "n_matched_reference": int(len(matched_ref)),
        "by_protocol_class": by_class,
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "n_cohort": int(len(cohort)),
            "min_n_per_class": MIN_N_PER_CLASS,
            "matched_reference_source": "nhanes_pool_excluding_cohort",
            "n_matched_reference": int(len(matched_ref)),
        },
        methods={
            "phenoage": "Levine 2018 (NHANES precomputed)",
            "matching": "5y age band x sex x BMI band, 4:1",
            "uncertainty": "Monte Carlo 10,000 iterations, 95% CI",
            "multiple_comparison_correction": "Benjamini-Hochberg FDR at 0.05",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_healthspan"],
        synthetic_data_flag=True,
        notes=[
            f"Synthetic Healthspan cohort with simulated -{abs(effect_size_years)} yr baseline effect.",
            "Production: replace generate_healthspan_cohort with bronze_healthspan_* read.",
        ],
    )
    write_run(output_dir, manifest, results, extras={"cohort": cohort, "matched_reference": matched_ref})
    log.info("==== HSH2 RUN COMPLETE: output=%s ====", output_dir)
    log.info("Class effects: %s", {k: (v.get("point_estimate") if "point_estimate" in v else None) for k, v in by_class.items()})
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--effect-size", type=float, default=-3.0)
    args = parser.parse_args()
    run(effect_size_years=args.effect_size)
