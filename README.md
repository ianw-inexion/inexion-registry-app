# INEXION Longevity Registry — App Prototype

**Version:** 0.2.0-prototype
**Stack:** Streamlit + DuckDB + Plotly
**Data source (prototype):** `inexion-registry-pipeline/data/staging/nhanes_with_phenoage.parquet`

---

## What this is

A clickable prototype of the INEXION Longevity Registry web application. Reads
directly from the existing pipeline's parquet output. No server to set up, no
database to migrate. The point of this build is to resolve interface design
questions by existing, not by spec.

Five pages:

1. **Landing / home** — registry overview, top-line stats, roadmap
2. **Dataset Catalog** — NHANES, HRS, UKB, CALERIE, GEO status
3. **Cohort Builder** — demographic + biomarker filters, live count, descriptive summary, histograms, cycle trends, CSV export
4. **Variable Dictionary** — every column in the harmonized dataset with unit, range, and definition
5. **Biological Age Calculator** — PhenoAge from 9 lab values + age
6. **Admin** — data freshness, coverage, what's pending for v0.3

---

## Run it

From this directory:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

**If the app errors on "data not found":** the prototype expects the NHANES
parquet at `../inexion-registry-pipeline/data/staging/nhanes_with_phenoage.parquet`
(relative to this folder). To point at a different path:

```bash
INEXION_DATA_DIR=/path/to/staging streamlit run app.py
```

---

## Not in this prototype (on purpose)

- No auth. Anyone who opens `localhost:8501` sees everything.
- No remote object storage. Reads local parquet.
- No audit logging.
- No public shell. The branded `registry.inexion.com` marketing surface is a
  separate Next.js project, not part of this app.
- No HRS/UKB/CALERIE/GEO data. Pipelines are built; data arrives when access
  does. Catalog page shows status.

All of this is scoped into the v0.3 deployment. See `PRD.md` for the full plan.

---

## Layout

```
inexion-registry-app/
├── app.py                       # Home
├── pages/
│   ├── 1_Dataset_Catalog.py
│   ├── 2_Cohort_Builder.py
│   ├── 3_Variable_Dictionary.py
│   ├── 4_Bioage_Calculator.py
│   └── 5_Admin.py
├── src/
│   ├── config.py                # Paths, brand colors, dataset catalog
│   ├── data.py                  # DuckDB queries, parameterized filters
│   ├── schema.py                # Variable dictionary + categorical labels
│   └── bioage.py                # PhenoAge formula for the calculator
├── .streamlit/config.toml       # Theme (navy / gold)
├── requirements.txt
├── README.md
└── PRD.md                       # Product requirements for v0.3 deployment
```

---

## Data contract this prototype assumes

`data/staging/nhanes_with_phenoage.parquet` with at least the following columns:

- Identifiers & design: `seqn`, `cycle`, `cycle_start_year`, `exam_weight`
- Demographics: `age`, `sex`, `race_ethnicity`, `education`, `income_ratio`
- Anthropometrics: `bmi`, `waist_cm`, `weight_kg`, `height_cm`
- Blood pressure: `systolic_mean`, `diastolic_mean`, `pulse`
- PhenoAge biomarkers: `albumin`, `creatinine`, `glucose_biopro`, `ln_crp`,
  `crp`, `lymphocyte_pct`, `mcv`, `rdw`, `alkaline_phosphatase`, `wbc`
- KDM extras: `total_cholesterol`, `bun`, `uric_acid`
- Metabolic: `hba1c`, `fasting_glucose`, `fasting_insulin`, `homa_ir`
- Lipids: `hdl`, `non_hdl_cholesterol`
- Biological age outputs: `phenoage`, `phenoage_delta`, `kdm_bioage`, `kdm_advance`

Schema changes in the pipeline are additive-safe — the app tolerates extra
columns. Rename of an existing column will break a single query; fix in `src/data.py`.
