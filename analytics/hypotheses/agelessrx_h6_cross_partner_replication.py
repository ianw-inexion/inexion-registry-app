"""
AgelessRx H6 — Cross-partner replication (Healthspan and AgelessRx).

Hypothesis: When Healthspan and AgelessRx cohorts are independently matched
against NHANES and analyzed under the same PhenoAge methodology, both produce
directionally consistent negative PhenoAge deltas for patients on similar
intervention classes. Effect-size estimates fall within overlapping 95% intervals.

This is the highest-strategic finding the registry can produce per the v3
Engagement Hypotheses doc. It demonstrates that the cross-partner architecture
yields independent replication — the credential pharma analytics teams care
about above all.

Pattern: Bronze read for both partners -> match each independently to NHANES ->
compute PhenoAge delta with MC CI for each -> overlap assessment of 95% CIs.
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
from analytics.lib.synth import generate_agelessrx_cohort, generate_healthspan_cohort

HYPOTHESIS_ID = "AGELESSRX_H6"
HYPOTHESIS_TITLE = "Cross-partner replication: Healthspan and AgelessRx"
log = logging.getLogger("ARXH6")


def _intervals_overlap(a_lo, a_hi, b_lo, b_hi) -> bool:
    return not (a_hi < b_lo or b_hi < a_lo)


def run(hs_effect: float = -3.0, arx_effect_mm: float = -4.5):
    rng = np.random.default_rng(20260520 + 6)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== ARXH6 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()

    # Healthspan arm
    hs_cohort, hs_idx = generate_healthspan_cohort(nhanes_all, effect_size_years=hs_effect, rng=rng)
    hs_ref_pool = nhanes_all.drop(index=hs_idx).copy()
    hs_matched = match_cohort_to_reference(hs_cohort, hs_ref_pool, rng=rng)
    hs_ci = monte_carlo_ci(
        cohort_deltas=hs_cohort["phenoage_delta"].values,
        reference_deltas=hs_matched["phenoage_delta"].values,
        rng=rng,
    )

    # AgelessRx arm (independent matching from same NHANES pool — INTENTIONAL)
    arx_cohort, arx_idx = generate_agelessrx_cohort(nhanes_all, multimodal_effect_years=arx_effect_mm, rng=rng)
    arx_ref_pool = nhanes_all.drop(index=arx_idx).copy()
    arx_matched = match_cohort_to_reference(arx_cohort, arx_ref_pool, rng=rng)
    arx_ci = monte_carlo_ci(
        cohort_deltas=arx_cohort["phenoage_delta"].values,
        reference_deltas=arx_matched["phenoage_delta"].values,
        rng=rng,
    )

    # Replication assessment
    same_direction = (hs_ci["point_estimate"] < 0) == (arx_ci["point_estimate"] < 0)
    intervals_overlap = _intervals_overlap(hs_ci["ci_low"], hs_ci["ci_high"], arx_ci["ci_low"], arx_ci["ci_high"])
    point_estimate_diff = arx_ci["point_estimate"] - hs_ci["point_estimate"]
    if hs_ci["point_estimate"] != 0:
        relative_difference_pct = 100.0 * abs(point_estimate_diff) / abs(hs_ci["point_estimate"])
    else:
        relative_difference_pct = float("nan")

    replication_verdict = (
        "STRONG" if (same_direction and intervals_overlap and relative_difference_pct < 30.0)
        else "DIRECTIONAL" if same_direction
        else "FAIL"
    )

    # Class-aligned subgroup: compare HRT in Healthspan vs Metformin in AgelessRx, etc.
    # (Same intervention class isn't always 1:1 across partners; use closest analogous class.)
    class_compare = {}
    common_classes = [("HRT", "RAPAMYCIN"), ("GLP1", "GLP1"), ("MULTI_MODAL", "multi_modal")]
    for hs_class, arx_class in common_classes:
        hs_sub = hs_cohort[hs_cohort.get("protocol_class") == hs_class] if "protocol_class" in hs_cohort.columns else hs_cohort.iloc[0:0]
        arx_sub = arx_cohort[arx_cohort.get("protocol_arm") == arx_class] if "protocol_arm" in arx_cohort.columns else arx_cohort.iloc[0:0]
        if len(hs_sub) < 50 or len(arx_sub) < 50:
            continue
        hs_sub_ci = monte_carlo_ci(
            cohort_deltas=hs_sub["phenoage_delta"].values,
            reference_deltas=hs_matched["phenoage_delta"].values, rng=rng,
        )
        arx_sub_ci = monte_carlo_ci(
            cohort_deltas=arx_sub["phenoage_delta"].values,
            reference_deltas=arx_matched["phenoage_delta"].values, rng=rng,
        )
        class_compare[f"{hs_class}__vs__{arx_class}"] = {
            "n_healthspan": int(len(hs_sub)),
            "n_agelessrx": int(len(arx_sub)),
            "healthspan_ci": hs_sub_ci,
            "agelessrx_ci": arx_sub_ci,
            "intervals_overlap": _intervals_overlap(
                hs_sub_ci["ci_low"], hs_sub_ci["ci_high"],
                arx_sub_ci["ci_low"], arx_sub_ci["ci_high"],
            ),
        }

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "healthspan": {
            "n_cohort": int(len(hs_cohort)),
            "n_matched_reference": int(len(hs_matched)),
            "phenoage_delta_difference": hs_ci,
        },
        "agelessrx": {
            "n_cohort": int(len(arx_cohort)),
            "n_matched_reference": int(len(arx_matched)),
            "phenoage_delta_difference": arx_ci,
        },
        "replication_assessment": {
            "same_direction": bool(same_direction),
            "intervals_overlap": bool(intervals_overlap),
            "point_estimate_difference_years": float(point_estimate_diff),
            "relative_difference_pct": float(relative_difference_pct) if relative_difference_pct == relative_difference_pct else None,
            "verdict": replication_verdict,
        },
        "by_intervention_class": class_compare,
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "healthspan_n": int(len(hs_cohort)),
            "agelessrx_n": int(len(arx_cohort)),
            "shared_reference": "NHANES 1999-2018 harmonized panel",
            "independent_matching": "Each partner matched separately to NHANES; replication assessed via 95% CI overlap",
        },
        methods={
            "phenoage": "Levine 2018 (NHANES precomputed)",
            "matching": "5y age band x sex x BMI band, 4:1, independent per partner",
            "uncertainty": "Monte Carlo 10,000 iterations, 95% CI per partner",
            "replication_criterion": "(1) same direction (2) overlapping 95% CIs (3) relative difference < 30%",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_healthspan", "synthetic_agelessrx"],
        synthetic_data_flag=True,
        notes=[
            "This is the most strategically valuable single finding the registry can produce per v3 Hypotheses doc.",
            "Production: replace generate_*_cohort functions with bronze_*_* Bronze reads.",
        ],
    )
    write_run(output_dir, manifest, results,
              extras={"healthspan_cohort": hs_cohort, "agelessrx_cohort": arx_cohort,
                      "healthspan_matched_reference": hs_matched,
                      "agelessrx_matched_reference": arx_matched})
    log.info("==== ARXH6 RUN COMPLETE: output=%s ====", output_dir)
    log.info("Healthspan Δ=%+.2f [%+.2f, %+.2f]", hs_ci["point_estimate"], hs_ci["ci_low"], hs_ci["ci_high"])
    log.info("AgelessRx  Δ=%+.2f [%+.2f, %+.2f]", arx_ci["point_estimate"], arx_ci["ci_low"], arx_ci["ci_high"])
    log.info("Replication verdict: %s (same direction=%s, intervals overlap=%s)",
             replication_verdict, same_direction, intervals_overlap)
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hs-effect", type=float, default=-3.0)
    parser.add_argument("--arx-effect-multimodal", type=float, default=-4.5)
    args = parser.parse_args()
    run(hs_effect=args.hs_effect, arx_effect_mm=args.arx_effect_multimodal)
