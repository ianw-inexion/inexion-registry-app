"""
Central configuration for the INEXION Registry app.

Three deployment modes, in priority order:

1. PRODUCTION TREE (S3, OMOP-aligned layout per Schema v0.3)
   Set: INEXION_BUCKET_ROOT=s3://inexion-registry
   Paths resolve as: <bucket_root>/<source-tree-prefix>/<filename>
   Example: s3://inexion-registry/bronze/public/nhanes/1999_2018/nhanes_with_phenoage.parquet

2. LEGACY FLAT (backward-compat for the sandbox era, kept as a safety net)
   Set: INEXION_DATA_DIR=s3://inexion-registry/temp_Ian_Nirav/staging
   or:  INEXION_DATA_DIR=/local/path/to/staging
   Paths resolve as: <data_dir>/<flat_filename>   (prefix ignored)

3. LOCAL DEFAULT (no env var set)
   Resolves to ../inexion-registry-pipeline/data/staging (flat)

Each data-path constant declares BOTH a tree prefix (for production) AND
a flat filename (for legacy). The path helper picks the right one based on
the active mode. This keeps the migration reversible: revert INEXION_BUCKET_ROOT
to INEXION_DATA_DIR and the app works against the old sandbox.
"""

from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
NAVY = "#0D1B3E"
GOLD = "#C9941A"
DARK_TEXT = "#1A1A2E"
LIGHT_BG = "#F5F5F7"
CORAL = "#E5735B"
TEAL = "#2E8B8B"

BRAND_COLORWAY = [NAVY, GOLD, TEAL, CORAL, "#6B6B8D", "#8B6B3E"]

# ---------------------------------------------------------------------------
# Mode resolution
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LOCAL = str(_REPO_ROOT.parent / "inexion-registry-pipeline" / "data" / "staging")

_BUCKET_ROOT_ENV = os.environ.get("INEXION_BUCKET_ROOT")
_DATA_DIR_ENV = os.environ.get("INEXION_DATA_DIR")

if _BUCKET_ROOT_ENV:
    MODE = "tree_s3"
    IS_S3 = True
    _ROOT = _BUCKET_ROOT_ENV.rstrip("/")
elif _DATA_DIR_ENV:
    MODE = "flat_legacy"
    IS_S3 = _DATA_DIR_ENV.startswith("s3://")
    _ROOT = _DATA_DIR_ENV.rstrip("/") if IS_S3 else _DATA_DIR_ENV
else:
    MODE = "flat_default"
    IS_S3 = False
    _ROOT = _DEFAULT_LOCAL


def _path(tree_prefix: str, tree_filename: str, flat_filename: str = None):
    """Build a FILE data path that works in all three modes.

    tree_prefix:    the S3-layout prefix (Schema v0.3), used in tree_s3 mode.
    tree_filename:  the filename within the tree prefix, used in tree_s3 mode.
    flat_filename:  the legacy filename within the flat staging dir.
                    If None, defaults to tree_filename (used when both layouts have the same filename).

    Returns str for S3, Path for local.
    """
    if flat_filename is None:
        flat_filename = tree_filename
    if MODE == "tree_s3":
        return f"{_ROOT}/{tree_prefix.strip('/')}/{tree_filename}"
    if IS_S3:
        return f"{_ROOT}/{flat_filename}"
    return Path(_ROOT) / flat_filename


def _path_dir(tree_prefix: str, flat_subdir: str):
    """Build a DIRECTORY data path that works in all three modes.

    tree_prefix: the S3-layout directory prefix (used as-is in tree_s3 mode).
    flat_subdir: the subdirectory under the legacy flat staging dir.

    Returns str for S3, Path for local.
    """
    if MODE == "tree_s3":
        return f"{_ROOT}/{tree_prefix.strip('/')}"
    if IS_S3:
        return f"{_ROOT}/{flat_subdir}"
    return Path(_ROOT) / flat_subdir


def data_exists(path) -> bool:
    """Check if a data file or prefix exists. Works for both local and S3."""
    if IS_S3:
        try:
            import s3fs
            fs = s3fs.S3FileSystem(anon=False)
            return fs.exists(str(path).replace("s3://", ""))
        except Exception:
            return False
    return Path(path).exists()


# Expose DATA_DIR for legacy code that uses it as a root pointer
DATA_DIR = Path(_ROOT) if not IS_S3 else _ROOT

# ---------------------------------------------------------------------------
# Data path constants
# Each constant declares its tree-mode prefix and its legacy flat filename.
# When INEXION_BUCKET_ROOT is set, paths use the tree layout.
# When INEXION_DATA_DIR is set, paths use the legacy flat layout.
# ---------------------------------------------------------------------------

# NHANES — Bronze, Public
NHANES_PARQUET            = _path("bronze/public/nhanes/1999_2018",       "nhanes_with_phenoage.parquet")
NHANES_HARMONIZED         = _path("bronze/public/nhanes/1999_2018",       "nhanes_harmonized.parquet")
NHANES_MORTALITY_PARQUET  = _path("bronze/public/nhanes/1999_2018",       "nhanes_with_mortality.parquet")

# HRS Public-use (RAND) — Bronze, Public
HRS_PUBLIC_PARQUET        = _path("bronze/public/hrs_public/2016",        "hrs_public_2016.parquet")

# HRS Restricted Data Agreement — Bronze, Restricted
HRS_VBS_PARQUET           = _path("bronze/restricted/hrs_rda/vbs_2016",          "hrs_vbs_with_phenoage.parquet")
HRS_DBS_PARQUET           = _path("bronze/restricted/hrs_rda/dbs_2006_2016",     "hrs_dbs_longitudinal.parquet")
HRS_EPIGEN_PARQUET        = _path("bronze/restricted/hrs_rda/epigen_2016",       "hrs_epigenetic_clocks.parquet")
HRS_POA_PARQUET           = _path("bronze/restricted/hrs_rda/poa",               "hrs_paceofaging.parquet")
HRS_MORTALITY_PARQUET     = _path("bronze/restricted/hrs_rda/mortality",         "hrs_mortality.parquet")

# MIDUS — Bronze, Public (ICPSR registration)
MIDUS_BIO_PARQUET         = _path("bronze/public/midus/biomarker",        "midus_biomarker.parquet")
MIDUS_COG_PARQUET         = _path("bronze/public/midus/cognitive_m3",     "midus_cognitive_m3.parquet")
MIDUS_CODEBOOK_PARQUET    = _path("bronze/public/midus/_meta",            "midus_codebook.parquet")
MIDUS_MORTALITY_PARQUET   = _path("bronze/public/midus/mortality",        "midus_mortality.parquet")

# NSHAP — Bronze, Public (ICPSR + restricted overlay)
NSHAP_BIO_PARQUET         = _path("bronze/public/nshap/biomarker",        "nshap_biomarker.parquet")
NSHAP_SOCIAL_PARQUET      = _path("bronze/public/nshap/social",           "nshap_social.parquet")
NSHAP_CODEBOOK_PARQUET    = _path("bronze/public/nshap/_meta",            "nshap_codebook.parquet")

# BRFSS — Bronze, Public
BRFSS_STATE_PARQUET       = _path("bronze/public/brfss/2024",             "brfss_state_scores.parquet")
BRFSS_METRO_PARQUET       = _path("bronze/public/brfss/2024",             "brfss_metro_scores.parquet")

# GEO molecular-aging reference — Bronze, Public
GEO_PANEL_PARQUET         = _path("bronze/public/geo/_panel",             "geo_aging_panel.parquet")
GEO_CATALOG_PARQUET       = _path("bronze/public/geo/datasets", "catalog_summary.parquet", "geo/catalog_summary.parquet")
GEO_DATASET_DIR           = _path_dir("bronze/public/geo/datasets",       "geo")

# Clinic data layer (synthetic seed today) — Derived
CLINIC_PATIENTS_PARQUET      = _path("derived/clinic_synthetic_10k", "clinic_patients.parquet",              "clinic/clinic_patients.parquet")
CLINIC_VISITS_PARQUET        = _path("derived/clinic_synthetic_10k", "clinic_visits.parquet",                "clinic/clinic_visits.parquet")
CLINIC_INTERVENTIONS_PARQUET = _path("derived/clinic_synthetic_10k", "clinic_interventions.parquet",         "clinic/clinic_interventions.parquet")
CLINIC_NOTES_PARQUET         = _path("derived/clinic_synthetic_10k", "clinic_notes.parquet",                 "clinic/clinic_notes.parquet")
CLINIC_CLOCKS_PARQUET        = _path("derived/clinic_synthetic_10k", "clinic_clocks.parquet",                "clinic/clinic_clocks.parquet")
CLINIC_TAXONOMY_PARQUET      = _path("derived/clinic_synthetic_10k", "clinic_intervention_taxonomy.parquet", "clinic/clinic_intervention_taxonomy.parquet")
CLINIC_RESPONSE_PARQUET      = _path("derived/clinic_synthetic_10k", "clinic_response_analytics.parquet",    "clinic/clinic_response_analytics.parquet")
CLINIC_WORKBENCH_PARQUET     = _path("derived/clinic_synthetic_10k", "clinic_workbench.parquet",             "clinic/clinic_workbench.parquet")

# Headline analyses — Derived
HEADLINE_DIR              = _path_dir("derived/headline_analyses",        "headline_analyses")

# Organ clocks — Derived
ORGAN_CLOCKS_PARAMS_PATH      = _path("derived/organ_clocks",             "organ_clocks_params.json")
ORGAN_CLOCKS_VALIDATION_PATH  = _path("derived/organ_clocks",             "organ_clocks_validation.json")

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_TITLE = "INEXION Longevity Registry"
APP_TAGLINE = "INEXION Longevity Registry"
APP_VERSION = "0.3.0-prototype"

# ---------------------------------------------------------------------------
# Dataset catalog (unchanged from prior version)
# ---------------------------------------------------------------------------
DATASETS = [
    {
        "id": "inexion_clinic",
        "name": "INEXION Clinic Layer (synthetic_10k)",
        "source": "INEXION-operated longevity clinics (first-party)",
        "status": "Available - synthetic seed",
        "access": "Internal / partner clinics (HIPAA-de-identified)",
        "participants": 10000,
        "cycles": None,
        "cycle_range": "Longitudinal, ~4.5 visits/patient",
        "description": (
            "INEXION's first-party longitudinal clinic registry. Each clinic "
            "submits a 4-CSV bundle (patients, lab results, interventions, "
            "physician notes) and the pipeline produces five harmonized "
            "parquets: clinic_patients, clinic_visits (70-marker lab panel), "
            "clinic_interventions (mapped against a 44-entry INEXION "
            "taxonomy with therapeutic class, mechanism class, ATC code, "
            "and INEXION namespace code), clinic_notes (PII-scrubbed), and "
            "clinic_clocks (PhenoAge, Liver Age, Kidney Age per visit, "
            "plus baseline-anchored trajectory deltas). De-identification: "
            "SHA256 patient-ID hashing + per-patient deterministic date "
            "shift (±90 days) preserves intervals while breaking "
            "calendar linkage. Current seed is a synthetic 10K-patient "
            "cohort; the same pipeline absorbs real Healthspan data "
            "when it lands."
        ),
        "path": CLINIC_PATIENTS_PARQUET,
    },
    {
        "id": "nhanes",
        "name": "NHANES 2001-2018",
        "source": "CDC National Health and Nutrition Examination Survey",
        "status": "Available",
        "access": "Public",
        "participants": 44898,
        "cycles": 9,
        "cycle_range": "2001-2018",
        "description": (
            "Nationally representative U.S. adult cohort with harmonized clinical "
            "biomarkers (CBC, CMP, lipids, CRP, HbA1c), anthropometrics, blood "
            "pressure, and demographics. PhenoAge and KDM biological age computed "
            "per participant. Secular trend finding: U.S. adults aged 40-60 are "
            "biologically aging 6.8 years faster than in 2009."
        ),
        "path": NHANES_PARQUET,
    },
    {
        "id": "hrs_vbs",
        "name": "HRS 2016 - Venous Blood Study (PhenoAge)",
        "source": "University of Michigan / NIA - Restricted Access",
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
        "name": "HRS DBS Longitudinal Biomarkers (2006-2016)",
        "source": "University of Michigan / NIA - Restricted Access",
        "status": "Available",
        "access": "Restricted Data Agreement",
        "participants": 22378,
        "cycles": 6,
        "cycle_range": "2006-2016 (6 waves)",
        "description": (
            "Dried Blood Spot biomarker panels across 6 waves (2006-2016) for "
            "22,378 unique HRS respondents. Variables: HbA1c, HDL cholesterol, "
            "total cholesterol, CRP, and cystatin-C. Enables longitudinal "
            "biomarker trajectory analysis - who ages fast vs. slow over a decade "
            "and what predicts it."
        ),
        "path": HRS_DBS_PARQUET,
    },
    {
        "id": "hrs_clocks",
        "name": "HRS Epigenetic Clocks (GrimAge2 + DunedinPACE)",
        "source": "University of Michigan / NIA - Restricted Access",
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
        "source": "University of Michigan / NIA - Researcher Contribution",
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
        "name": "HRS 2016 - Public Survey Data",
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
        "id": "midus_biomarker",
        "name": "MIDUS Biomarker (M2 + Refresher 1 + M3)",
        "source": "ICPSR / University of Wisconsin-Madison",
        "status": "Available",
        "access": "Public (ICPSR registration)",
        "participants": 2865,
        "cycles": 3,
        "cycle_range": "2004-2022 (3 waves)",
        "description": (
            "Three MIDUS biomarker waves stacked and harmonized: M2 (n=1,255, "
            "2004-2009), Refresher 1 (n=863, 2012-2016), and M3 (n=747, "
            "2017-2022). 51 harmonized variables: cardiometabolic panel "
            "(HbA1c, lipids, glucose, insulin, HOMA-IR, creatinine, eGFR), "
            "comprehensive inflammation suite (CRP, IL-6, IL-8, IL-10, TNF-alpha, "
            "fibrinogen, sICAM-1, sE-selectin, sUPAR), neuroendocrine "
            "(DHEA, DHEA-S, IGF-1, urinary cortisol, catecholamines), bone "
            "turnover (P1NP, NTx, BAP), anthropometry (BMI, WHR), and BP. "
            "KDM biological age computed with 5 inputs (no serum albumin in "
            "MIDUS - B4BALBUMIN is urinary). Canonical PhenoAge cannot be "
            "computed: MIDUS lacks WBC, MCV, RDW, lymphocyte%, and total ALP. "
            "MIDUS is the registry's allostatic-load and inflammation-aging "
            "reference cohort."
        ),
        "path": MIDUS_BIO_PARQUET,
    },
    {
        "id": "midus_cognitive_m3",
        "name": "MIDUS 3 Cognitive (BTACT)",
        "source": "ICPSR / University of Wisconsin-Madison",
        "status": "Available",
        "access": "Public (ICPSR registration)",
        "participants": 3291,
        "cycles": 1,
        "cycle_range": "2013-2017",
        "description": (
            "Brief Test of Adult Cognition by Telephone (BTACT) battery for "
            "3,291 MIDUS 3 respondents. Variables: word-list immediate recall "
            "(unique/repeats/intrusions), digit span backward, category "
            "fluency, number series first-pass, stop-and-go switch task "
            "composites. Pairs with the MIDUS biomarker file via M2ID for "
            "cross-domain biomarker -> cognition analyses."
        ),
        "path": MIDUS_COG_PARQUET,
    },
    {
        "id": "nshap",
        "access": "Public (ICPSR registration) + Restricted (IRB + DPP + DUA)",
        "participants": 12000,
        "cycles": 4,
        "cycle_range": "2005-2023 (4 rounds)",
        "description": (
            "National Social Life, Health, and Aging Project. 4 longitudinal rounds "
            "of older U.S. adults (57-85 at baseline). DBS biomarker panel from "
            "Round 2 onward (HbA1c, CRP, total chol, hemoglobin, EBV/CMV antibodies). "
            "Salivary cortisol from Round 1. Distinctive vs HRS / MIDUS: in-home "
            "social-network roster, sensory measures (smell, hearing, peak flow), "
            "functional measures (grip, gait). Public-use available via ICPSR; "
            "restricted-use NDI mortality linkage requires IRB + DPP + DUA. "
            "Pipeline: build_nshap_parquet.py (scaffolded, awaiting raw data)."
        ),
        "path": NSHAP_BIO_PARQUET,
    },
    {
        "id": "ukb",
        "name": "UK Biobank",
        "source": "UK Biobank",
        "status": "Application in progress",
        "access": "Material Transfer Agreement",
        "participants": 500000,
        "cycles": 2,
        "cycle_range": "2006-2023",
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
        "cycle_range": "Baseline-24mo",
        "description": (
            "Randomized controlled trial of 25% caloric restriction in healthy "
            "non-obese adults. Key intervention dataset for demonstrating "
            "biological age reversibility. DunedinPACE responded significantly "
            "in the CALERIE trial - validates rate-of-aging as intervention endpoint."
        ),
        "path": None,
    },
    {
        "id": "geo",
        "name": "GEO Molecular Aging Reference",
        "source": "NCBI GEO + Zenodo + Allen Institute Immune Atlas",
        "status": "Available",
        "access": "Public",
        "participants": 2480,
        "cycles": 15,
        "cycle_range": "Cross-sectional + intervention",
        "description": (
            "15 curated transcriptomics datasets - the molecular reference layer "
            "for the INEXION multi-omic platform."
        ),
        "path": GEO_CATALOG_PARQUET,
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
            "Variables: income, exercise, health coverage, metro status."
        ),
        "path": None,
    },
]
