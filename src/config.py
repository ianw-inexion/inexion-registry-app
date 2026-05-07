"""
Central configuration for the INEXION Registry app prototype.

Path resolution lets the app run from two places:
- Inside this repo (default): parquet lives in the sibling pipeline folder
- Pointed at an override path via INEXION_DATA_DIR env var
"""
from pathlib import Path
import os

# ── Brand ────────────────────────────────────────────────────────────────────
NAVY = "#0D1B3E"
GOLD = "#C9941A"
DARK_TEXT = "#1A1A2E"
LIGHT_BG = "#F5F5F7"
CORAL = "#E5735B"
TEAL = "#2E8B8B"

BRAND_COLORWAY = [NAVY, GOLD, TEAL, CORAL, "#6B6B8D", "#8B6B3E"]

# ── Data paths ───────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DATA = _REPO_ROOT.parent / "inexion-registry-pipeline" / "data" / "staging"

DATA_DIR = Path(os.environ.get("INEXION_DATA_DIR", _DEFAULT_DATA))

NHANES_PARQUET = DATA_DIR / "nhanes_with_phenoage.parquet"
NHANES_HARMONIZED = DATA_DIR / "nhanes_harmonized.parquet"
HRS_PUBLIC_PARQUET = DATA_DIR / "hrs_public_2016.parquet"
HRS_VBS_PARQUET = DATA_DIR / "hrs_vbs_with_phenoage.parquet"

HEADLINE_DIR = DATA_DIR / "headline_analyses"

# ── App metadata ─────────────────────────────────────────────────────────────
APP_TITLE = "INEXION Longevity Registry"
APP_TAGLINE = "INEXION Longevity Registry"
APP_VERSION = "0.2.0-prototype"

# ── Dataset catalog ──────────────────────────────────────────────────────────
# This drives the catalog page. New datasets get added here when they arrive.
DATASETS = [
    {
        "id": "nhanes",
        "name": "NHANES 1999–2018",
        "source": "CDC National Health and Nutrition Examination Survey",
        "status": "Available",
        "access": "Public",
        "participants": 55081,
        "cycles": 10,
        "cycle_range": "1999–2018",
        "description": (
            "Nationally representative U.S. adult cohort with harmonized clinical "
            "biomarkers (CBC, CMP, lipids, CRP, HbA1c), anthropometrics, blood "
            "pressure, and demographics. PhenoAge and KDM biological age computed "
            "per participant."
        ),
        "path": NHANES_PARQUET,
    },
    {
        "id": "hrs",
        "name": "HRS (Health and Retirement Study)",
        "source": "University of Michigan / NIA",
        "status": "Available",
        "access": "Public (survey data) + Restricted Data Agreement (biomarkers)",
        "participants": 20912,
        "cycles": 1,
        "cycle_range": "2016 (Wave 13)",
        "description": (
            "Longitudinal U.S. cohort aged 50+. Public wave loaded: 2016 survey data "
            "including demographics, self-rated health, chronic conditions, ADL/IADL "
            "functional limitations, cognitive scores (word recall, serial 7s), "
            "lifestyle factors, and Fat File physical measures. "
            "Biomarker data (PhenoAge inputs) pending Restricted Data Agreement."
        ),
        "path": HRS_PUBLIC_PARQUET,
    },
    {
        "id": "ukb",
        "name": "UK Biobank",
        "source": "UK Biobank",
        "status": "Application in progress",
        "access": "Material Transfer Agreement",
        "participants": 500000,
        "cycles": 2,
        "cycle_range": "2006–2023",
        "description": (
            "~500K participants with baseline and repeat-assessment biomarkers. "
            "PhenoAge + KDM field mapping complete. Repeat assessment subset "
            "(~20K) enables longitudinal biological age trajectories."
        ),
        "path": None,
    },
    {
        "id": "calerie",
        "name": "CALERIE Phase 2",
        "source": "NIA / NIDDK",
        "status": "Access not yet initiated",
        "access": "IRB + DUA",
        "participants": 218,
        "cycles": 5,
        "cycle_range": "Baseline–24mo",
        "description": (
            "Randomized controlled trial of 25% caloric restriction in healthy "
            "non-obese adults. Key intervention dataset for demonstrating "
            "biological age reversibility."
        ),
        "path": None,
    },
    {
        "id": "geo",
        "name": "GEO Molecular Aging Reference",
        "source": "NCBI Gene Expression Omnibus",
        "status": "P1 series ready to download",
        "access": "Public",
        "participants": 2480,
        "cycles": None,
        "cycle_range": "Cross-sectional + intervention",
        "description": (
            "15 curated transcriptomics datasets spanning blood immune aging, "
            "senescence/SASP signatures, intervention response, and multi-tissue "
            "atlases. Molecular reference layer for the INEXION multi-omic platform."
        ),
        "path": None,
    },
]
