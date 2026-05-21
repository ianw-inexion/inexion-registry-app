"""
Synthetic cohort generators for pre-DUA prototyping.

Each generator synthesizes a partner-like cohort from NHANES with simulated
treatment-effect perturbations. Tagged synthetic in every analysis run manifest.

Production replacement: each generator's signature stays the same; the body is
replaced with a real Bronze read once the partner DUA executes.

    generate_healthspan_cohort   -> bronze_healthspan_* tables
    generate_agelessrx_cohort    -> bronze_agelessrx_* tables
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HEALTHSPAN_PROTOCOL_CLASSES = ["HRT", "GLP1", "NAD_PRECURSOR", "MULTI_MODAL", "PEPTIDES"]
HEALTHSPAN_CLASS_WEIGHTS    = [0.30, 0.25, 0.15, 0.20, 0.10]

AGELESSRX_PROTOCOL_CLASSES  = ["RAPAMYCIN", "METFORMIN", "NAD_PRECURSOR", "GLP1", "LDN", "PEPTIDES"]


def generate_healthspan_cohort(
    nhanes_pool: pd.DataFrame,
    effect_size_years: float = -3.0,
    effect_sd: float = 1.5,
    n_cohort: int = 1500,
    age_range: tuple[int, int] = (35, 75),
    bmi_range: tuple[float, float] = (20, 45),
    rng: np.random.Generator | None = None,
) -> tuple[pd.DataFrame, list[int]]:
    """Synthesize a Healthspan-like cohort with multi-protocol metadata."""
    rng = rng or np.random.default_rng(20260520)

    eligible = nhanes_pool[
        (nhanes_pool["age"].between(*age_range))
        & (nhanes_pool["bmi"].between(*bmi_range))
    ].copy()
    n_cohort = min(n_cohort, len(eligible))

    weights = np.where(eligible["bmi"].values >= 27, 1.5, 1.0)
    weights = weights / weights.sum()
    idx = rng.choice(eligible.index.values, size=n_cohort, replace=False, p=weights)
    cohort = eligible.loc[idx].copy().reset_index(drop=True)

    perturbation = rng.normal(loc=effect_size_years, scale=effect_sd, size=len(cohort))
    cohort["phenoage"] = cohort["phenoage"] + perturbation
    cohort["phenoage_delta"] = cohort["phenoage"] - cohort["age"]

    cohort["source"] = "healthspan_synthetic"
    cohort["protocol_class"] = rng.choice(
        HEALTHSPAN_PROTOCOL_CLASSES, size=len(cohort), p=HEALTHSPAN_CLASS_WEIGHTS
    )
    cohort["months_on_protocol"] = rng.integers(low=12, high=36, size=len(cohort))
    cohort["retained_12mo"] = rng.random(len(cohort)) > 0.18  # 82% retention at 12mo
    # Drop-offs systematically have higher baseline PhenoAge delta (retention bias)
    dropoff_mask = ~cohort["retained_12mo"]
    cohort.loc[dropoff_mask, "phenoage_delta"] += rng.normal(2.0, 0.8, dropoff_mask.sum())

    # Synthetic lifestyle covariates (NHANES native are limited; we add smoking + activity)
    cohort["smoking_status"] = rng.choice(
        ["never", "former", "current"], size=len(cohort), p=[0.55, 0.30, 0.15]
    )
    cohort["activity_level"] = rng.choice(
        ["low", "moderate", "high"], size=len(cohort), p=[0.30, 0.50, 0.20]
    )

    return cohort, idx.tolist()


def generate_agelessrx_cohort(
    nhanes_pool: pd.DataFrame,
    multimodal_effect_years: float = -4.5,
    rapamycin_effect_years: float = -3.5,
    single_arm_effect_years: float = -2.0,
    effect_sd: float = 1.5,
    n_cohort: int = 1200,
    age_range: tuple[int, int] = (40, 80),
    rng: np.random.Generator | None = None,
) -> tuple[pd.DataFrame, list[int]]:
    """Synthesize an AgelessRx-like cohort with multi-arm and rapamycin metadata."""
    rng = rng or np.random.default_rng(20260520 + 1)

    eligible = nhanes_pool[
        nhanes_pool["age"].between(*age_range)
        & nhanes_pool["bmi"].between(18, 45)
    ].copy()
    n_cohort = min(n_cohort, len(eligible))

    idx = rng.choice(eligible.index.values, size=n_cohort, replace=False)
    cohort = eligible.loc[idx].copy().reset_index(drop=True)

    # Assign protocol arms
    arms = rng.choice(
        ["multi_modal", "rapamycin_only", "metformin_only", "nad_only", "ldn"],
        size=len(cohort), p=[0.25, 0.30, 0.15, 0.15, 0.15],
    )
    cohort["protocol_arm"] = arms
    cohort["on_rapamycin"] = np.isin(arms, ["multi_modal", "rapamycin_only"])
    cohort["concurrent_protocol_count"] = np.where(arms == "multi_modal", rng.integers(3, 6, len(cohort)), 1)
    cohort["rapamycin_dose_mg_weekly"] = np.where(
        cohort["on_rapamycin"], rng.choice([3.0, 5.0, 6.0, 8.0], len(cohort)), 0.0
    )

    # Apply effect by arm
    effects = np.where(
        arms == "multi_modal", multimodal_effect_years,
        np.where(arms == "rapamycin_only", rapamycin_effect_years, single_arm_effect_years),
    )
    perturbation = rng.normal(loc=effects, scale=effect_sd)
    cohort["phenoage"] = cohort["phenoage"] + perturbation
    cohort["phenoage_delta"] = cohort["phenoage"] - cohort["age"]

    cohort["source"] = "agelessrx_synthetic"
    cohort["months_on_protocol"] = rng.integers(low=12, high=48, size=len(cohort))
    cohort["pearl_alumni"] = (rng.random(len(cohort)) < 0.15) & cohort["on_rapamycin"]

    # Lifestyle covariates
    cohort["smoking_status"] = rng.choice(
        ["never", "former", "current"], size=len(cohort), p=[0.60, 0.30, 0.10]
    )
    cohort["activity_level"] = rng.choice(
        ["low", "moderate", "high"], size=len(cohort), p=[0.20, 0.45, 0.35]
    )

    return cohort, idx.tolist()


def generate_longitudinal_timepoints(
    baseline_cohort: pd.DataFrame,
    n_timepoints: int = 4,
    months_between: int = 6,
    response_trajectory: str = "exponential_plateau",
    final_effect_factor: float = 1.0,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """
    Expand a baseline cohort into a longitudinal DataFrame with multiple timepoints
    per patient. PhenoAge delta evolves over time following the chosen trajectory.

    response_trajectory:
        "linear"               -- delta improves linearly with time
        "exponential_plateau"  -- delta improves fast then plateaus (default)
        "linear_then_plateau"  -- delta improves linearly for ~12mo then plateaus
    """
    rng = rng or np.random.default_rng(20260520 + 2)
    rows = []
    for _, p in baseline_cohort.iterrows():
        for t in range(n_timepoints):
            months = t * months_between
            if response_trajectory == "linear":
                progress = months / (n_timepoints * months_between)
            elif response_trajectory == "linear_then_plateau":
                progress = min(months / 12.0, 1.0)
            else:  # exponential_plateau
                progress = 1.0 - np.exp(-months / 9.0)
            current_perturbation = progress * final_effect_factor * (p["phenoage_delta"] - p["age"] + p["age"])  # carry forward
            # Cleaner: just scale the existing delta
            current_delta = p["phenoage_delta"] * progress + rng.normal(0, 0.5)
            current_phenoage = p["age"] + current_delta
            rows.append({
                **p.to_dict(),
                "timepoint_month": months,
                "timepoint_idx": t,
                "phenoage": current_phenoage,
                "phenoage_delta": current_delta,
            })
    return pd.DataFrame(rows)
