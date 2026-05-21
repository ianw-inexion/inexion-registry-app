"""
AgelessRx H2 — Rapamycin signal in real-world cohort vs PEARL trial.

Hypothesis: PhenoAge and inflammation-marker trajectories in AgelessRx real-world
rapamycin users at matched dose are directionally consistent with the PEARL
trial results (Aging, May 2025). Effect-size attenuation in real-world use is
no greater than 40% relative to the RCT estimate.

Pattern: Bronze read -> rapamycin subcohort -> matched NHANES reference -> compute
PhenoAge delta -> compare against PEARL trial published effect sizes.

PEARL reference effects from Aging 2025 publication (placeholder values for
the worked example; actual published effects to be plugged in from Mannick or
Kraft et al. when the analysis goes to production).
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

HYPOTHESIS_ID = "AGELESSRX_H2"
HYPOTHESIS_TITLE = "Rapamycin real-world vs PEARL trial"

# Published PEARL effect sizes (placeholder — replace with actual published numbers)
PEARL_PUBLISHED_PHENOAGE_DELTA_YRS = -2.6   # placeholder
PEARL_PUBLISHED_HSCRP_PCT_CHANGE  = -22.0   # placeholder

MAX_ALLOWED_ATTENUATION_PCT = 40.0
log = logging.getLogger("ARXH2")


def run():
    rng = np.random.default_rng(20260520 + 2)
    output_dir, run_id, started_at = make_run_dir(HYPOTHESIS_ID)
    log.info("==== ARXH2 RUN START: run_id=%s ====", run_id)

    nhanes_all = load_nhanes_reference()
    cohort_full, used_idx = generate_agelessrx_cohort(nhanes_all, rng=rng)

    rapamycin_cohort = cohort_full[cohort_full["on_rapamycin"]].copy()
    if len(rapamycin_cohort) < 50:
        log.warning("Rapamycin subcohort small (n=%d). Result will be wide-CI.", len(rapamycin_cohort))

    reference_pool = nhanes_all.drop(index=used_idx).copy()
    matched_ref = match_cohort_to_reference(rapamycin_cohort, reference_pool, rng=rng)

    rwe_ci = monte_carlo_ci(
        cohort_deltas=rapamycin_cohort["phenoage_delta"].values,
        reference_deltas=matched_ref["phenoage_delta"].values,
        rng=rng,
    )

    # Attenuation calculation: real-world effect vs PEARL published effect
    rwe_effect = rwe_ci["point_estimate"]
    if PEARL_PUBLISHED_PHENOAGE_DELTA_YRS != 0:
        attenuation_pct = 100.0 * (1.0 - rwe_effect / PEARL_PUBLISHED_PHENOAGE_DELTA_YRS)
    else:
        attenuation_pct = float("nan")
    within_threshold = attenuation_pct <= MAX_ALLOWED_ATTENUATION_PCT

    # Dose-effect stratification within rapamycin cohort
    by_dose = {}
    for dose, group in rapamycin_cohort.groupby("rapamycin_dose_mg_weekly"):
        if len(group) < 30:
            continue
        ci = monte_carlo_ci(
            cohort_deltas=group["phenoage_delta"].values,
            reference_deltas=matched_ref["phenoage_delta"].values,
            rng=rng,
        )
        by_dose[f"{dose:.1f}_mg_weekly"] = {"n": int(len(group)), **ci}

    results = {
        "hypothesis_id": HYPOTHESIS_ID,
        "hypothesis_title": HYPOTHESIS_TITLE,
        "n_rapamycin_cohort": int(len(rapamycin_cohort)),
        "n_matched_reference": int(len(matched_ref)),
        "real_world_phenoage_delta_difference": rwe_ci,
        "pearl_published_phenoage_delta_yrs": PEARL_PUBLISHED_PHENOAGE_DELTA_YRS,
        "attenuation_pct_vs_pearl": float(attenuation_pct) if attenuation_pct == attenuation_pct else None,
        "within_40pct_attenuation_threshold": bool(within_threshold) if within_threshold == within_threshold else None,
        "by_dose": by_dose,
    }

    manifest = RunManifest(
        run_id=run_id, hypothesis_id=HYPOTHESIS_ID,
        cohort_definition={
            "n_rapamycin_cohort": int(len(rapamycin_cohort)),
            "n_matched_reference": int(len(matched_ref)),
            "rapamycin_definition": "any active rapamycin protocol (mono or multi-modal)",
        },
        methods={
            "phenoage": "Levine 2018 (NHANES precomputed)",
            "matching": "5y age band x sex x BMI band, 4:1",
            "uncertainty": "Monte Carlo 10,000 iterations, 95% CI",
            "pearl_reference": "Placeholder published values — replace with Mannick/Kraft Aging 2025 estimates",
        },
        reference_cohort_version="nhanes_1999_2018_harmonized_v1",
        code_commit_hash=code_commit_hash(), ran_at=started_at,
        output_uri=str(output_dir),
        data_partner_ids=["synthetic_agelessrx"],
        synthetic_data_flag=True,
        notes=[
            "PEARL published effect sizes are placeholder; replace with actual published numbers before partner share.",
            "Production: bronze_agelessrx_interventions filter for rapamycin + dose mapping.",
        ],
    )
    write_run(output_dir, manifest, results,
              extras={"cohort": rapamycin_cohort, "matched_reference": matched_ref})
    log.info("==== ARXH2 RUN COMPLETE: output=%s ====", output_dir)
    log.info("Real-world Δ=%+.2f vs PEARL %+.2f | attenuation=%.1f%% (within 40%%: %s)",
             rwe_effect, PEARL_PUBLISHED_PHENOAGE_DELTA_YRS, attenuation_pct, within_threshold)
    return {"manifest": manifest.to_dict(), "results": results, "output_dir": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    run()
