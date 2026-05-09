"""
Central configuration for the INEXION Registry app prototype.

Supports three deployment modes:
- Local (default): parquet lives in the sibling pipeline folder
- S3: set INEXION_DATA_DIR=s3://inexion-registry/temp_Ian_Nirav/staging
- Streamlit Cloud: secrets auto-loaded in app.py → env vars → picked up here
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

# ── Data path resolution ──────────────────────────────────────────────────────
_REPO_ROOT   = Path(__file__).resolve().parent.parent
_DEFAULT_DATA = str(_REPO_ROOT.parent / "inexion-registry-pipeline" / "data" / "staging")
_DATA_DIR_RAW = os.environ.get("INEXION_DATA_DIR", _DEFAULT_DATA)

IS_S3 = _DATA_DIR_RAW.startswith("s3://")

def _dp(filename: str):
    """Build a data path — returns str for S3, Path for local."""
    if IS_S3:
        return f"{_DATA_DIR_RAW.rstrip('/')}/{filename}"
    return Path(_DATA_DIR_RAW) / filename

def data_exists(path) -> bool:
    """Check if a data file exists — works for both local and S3."""
    if IS_S3:
        try:
            import s3fs
            fs = s3fs.S3FileSystem(anon=False)
            return fs.exists(str(path).replace("s3://", ""))
        except Exception:
            return False
    return Path(path).exists()

# Expose DATA_DIR for legacy code that uses it as a Path
DATA_DIR = Path(_DATA_DIR_RAW) if not IS_S3 else _DATA_DIR_RAW

NHANES_PARQUET       = _dp("nhanes_with_phenoage.parquet")
NHANES_HARMONIZED    = _dp("nhanes_harmonized.parquet")
HRS_PUBLIC_PARQUET   = _dp("hrs_public_2016.parquet")
HRS_VBS_PARQUET      = _dp("hrs_vbs_with_phenoage.parquet")
HRS_DBS_PARQUET      = _dp("hrs_dbs_longitudinal.parquet")
HRS_EPIGEN_PARQUET   = _dp("hrs_epigenetic_clocks.parquet")
HRS_POA_PARQUET      = _dp("hrs_paceofaging.parquet")
HEADLINE_DIR         = _dp("headline_analyses")

# ── App metadata ─────────────────────────────────────────────────────────────
APP_TITLE = "INEXION Longevity Registry"
APP_TAGLINE = "INEXION Longevity Registry"
APP_VERSION = "0.3.0-prototype"

# ── Dataset catalog ──────────────────────────────────────────────────────────
DATASETS = [
    {
        "id": "nhanes",
        "name": "NHANES 2001–2018",
        "source": "CDC National Health and Nutrition Examination Survey",
        "status": "Available",
        "access": "Public",
        "participants": 44898,
        "cycles": 9,
        "cycle_range": "2001–2018",
        "description": (
            "Nationally representative U.S. adult cohort with harmonized clinical "
            "biomarkers (CBC, CMP, lipids, CRP, HbA1c), anthropometrics, blood "
            "pressure, and demographics. PhenoAge and KDM biological age computed "
            "per participant. Secular trend finding: U.S. adults aged 40–60 are "
            "biologically aging 6.8 years faster than in 2009."
        ),
        "path": NHANES_PARQUET,
    },
    {
        "id": "hrs_vbs",
        "name": "HRS 2016 — Venous Blood Study (PhenoAge)",
        "source": "University of Michigan / NIA — Restricted Access",
        "status": "Available",
        "access": "Restricted Data Agreement",
        "participants": 9567,
        "cycles": 1,
        "cycle_range": "2016 (Wave 13)",
        "description": (
            "Venous blood biomarker panel from 9,567 HRS respondents aged 50+. "
            "All 9 PhenoAge inputs present (albumin, creatinine, glucose, CRP, "
            "lymphocyte %, MCV, RDW, alkaline phosphatase, WBC). PhenoAge computed; "
            "mean biological age acceleration +3.64 years. Key finding: adults in "
            "the highest PhenoAge acceleration quintile are nearly 2x as likely to "
            "be cognitively impaired as those in the lowest quintile (27.9% vs 14.2%)."
        ),
        "path": HRS_VBS_PARQUET,
    },
    {
        "id": "hrs_dbs",
        "name": "HRS DBS Longitudinal Biomarkers (2006–2016)",
        "source": "University of Michigan / NIA — Restricted Access",
        "status": "Available",
        "access": "Restricted Data Agreement",
        "participants": 22378,
        "cycles": 6,
        "cycle_range": "2006–2016 (6 waves)",
        "description": (
            "Dried Blood Spot biomarker panels across 6 waves (2006–2016) for "
            "22,378 unique HRS respondents. Variables: HbA1c, HDL cholesterol, "
            "total cholesterol, CRP, and cystatin-C. Enables longitudinal "
            "biomarker trajectory analysis — who ages fast vs. slow over a decade "
            "and what predicts it."
        ),
        "path": HRS_DBS_PARQUET,
    },
    {
        "id": "hrs_clocks",
        "name": "HRS Epigenetic Clocks (GrimAge2 + DunedinPACE)",
        "source": "University of Michigan / NIA — Restricted Access",
        "status": "Available",
        "access": "Restricted Data Agreement",
        "participants": 4018,
        "cycles": 1,
        "cycle_range": "2016 (Wave 13)",
        "description": (
            "DNA methylation-based biological age clocks for 4,018 HRS respondents. "
            "Includes GrimAge2 (mortality-trained epigenetic clock) and DunedinPACE "
            "(rate of aging from methylation). Overlaps with VBS PhenoAge sample "
            "enabling direct comparison of clinical biomarker vs. epigenetic clock "
            "approaches in the same individuals."
        ),
        "path": HRS_EPIGEN_PARQUET,
    },
    {
        "id": "hrs_poa",
        "name": "HRS Pace of Aging (DunedinPACE)",
        "source": "University of Michigan / NIA — Researcher Contribution",
        "status": "Available",
        "access": "Restricted Data Agreement",
        "participants": 13358,
        "cycles": None,
        "cycle_range": "Multi-wave baseline",
        "description": (
            "DunedinPACE estimates for 13,358 HRS respondents from the Balachandran "
            "et al. 2025 Nature Aging analysis. DunedinPACE measures the rate of "
            "biological aging (years of aging per calendar year); values >1.0 indicate "
            "faster-than-average aging. Mean: 1.49. Most sensitive clock for "
            "detecting intervention response."
        ),
        "path": HRS_POA_PARQUET,
    },
    {
        "id": "hrs_survey",
        "name": "HRS 2016 — Public Survey Data",
        "source": "University of Michigan / NIA",
        "status": "Available",
        "access": "Public (RAND HRS)",
        "participants": 20912,
        "cycles": 1,
        "cycle_range": "2016 (Wave 13)",
        "description": (
            "RAND HRS Longitudinal File + 2016 Fat File. Demographics, cognitive "
            "scores (word recall, serial 7s), ADL/IADL functional limitations, "
            "chronic conditions, self-rated health, lifestyle factors, and "
            "physical measures. Used for health outcomes analysis in the HRS Explorer."
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
            "biological age reversibility. DunedinPACE responded significantly "
            "in the CALERIE trial — validates rate-of-aging as intervention endpoint."
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
    {
        "id": "brfss",
        "name": "BRFSS 2024",
        "source": "CDC Behavioral Risk Factor Surveillance System",
        "status": "Available",
        "access": "Public",
        "participants": 457670,
        "cycles": 1,
        "cycle_range": "2024",
        "description": (
            "State-level health surveillance data for 457,670 U.S. adults. "
            "Variables: income, exercise, health coverage, metro status. "
            "Used for INEXION market targeting analysis. Top markets identified: "
            "DC corridor (MD/VA suburban MSA), MA, NH, UT, CO."
        ),
        "path": None,
    },
]
