# INEXION REGISTRY APP — STATUS
**Last Updated:** April 23, 2026

---

## Project Quick Context

Web application layer for INEXION Longevity Registry. Sits on top of `inexion-registry-pipeline`, reads its parquet output, and exposes the registry to three audiences: internal INEXION staff, invited external researchers, and the public (capability layer only). Built as a pilot to turn the pipeline from a notebook-only asset into a clickable product surface.

**Maintainer:** Ian Wendt | **CTO:** Nirav Vira
**Stack:** Streamlit + DuckDB + Plotly (prototype) → add Next.js public shell + Supabase Auth + Cloudflare R2 + Railway/Render (v0.3 deployed)
**Status:** Local prototype complete. PRD drafted. Awaiting decisions on six open questions before deployment build begins.

---

## Strategic Decisions Locked (2026-04-23)

| # | Decision | Choice |
|---|---|---|
| 1 | Audience scope for v0.2/v0.3 | Internal + select external researchers + public showcase layer |
| 2 | Domain and hosting | `registry.inexion.com`, minimal-ops platform |
| 3 | Public findings disclosure | NHANES headline findings held for data room only; public layer shows capability, not numbers |
| 4 | Auth model | Google Workspace SSO for internal, magic-link / invite code for external researchers |

Chosen architecture: **Path C hybrid** — public Next.js shell on Vercel for the unauthenticated marketing surface + Streamlit gated app on Railway/Render for the cohort explorer + Supabase for auth and audit + Cloudflare R2 for parquet storage.

---

## Completed This Session (2026-04-23)

- [x] Strategic discussion: user personas, use cases, three architectural paths evaluated
- [x] Architecture decision: Path C hybrid locked
- [x] Streamlit prototype scaffolded at `03-REGISTRY/product/inexion-registry-app/`
- [x] Six pages built: Home, Dataset Catalog, Cohort Builder, Variable Dictionary, Biological Age Calculator, Admin
- [x] DuckDB query layer with parameterized filters (no SQL injection surface)
- [x] Variable dictionary: 35 entries across 7 groups (demographics, anthropometrics, BP, PhenoAge biomarkers, KDM biomarkers, metabolic, lipids, biological age outputs)
- [x] Dataset catalog configured for 5 sources (NHANES available; HRS/UKB/CALERIE/GEO status flagged)
- [x] Self-contained PhenoAge math in `src/bioage.py` for the calculator page
- [x] INEXION brand theme applied (`.streamlit/config.toml`, navy #0D1B3E, gold #C9941A)
- [x] `README.md` with run instructions and data contract
- [x] `PRD.md` v0.3 deployed-pilot specification: 13 sections, week-by-week milestones, 6 open questions
- [x] Sanity checks: PhenoAge math on healthy-50 profile (46.3 yr, -3.70 delta), all files parse, sample cohort query (40–65, BMI>30, PhenoAge delta < -2) returns n=2,588
- [x] Bugfix: `distribution()` double-WHERE clause — would have thrown `ParserException` the first time any filter was applied with a histogram rendered
- [x] Post-fix full query-path regression: count, preview, summary, distribution, trend, export all pass on the specific filter combo that triggered the original error (n=1,187 women 40–65, BMI≥30, 2015–2018, mean PhenoAge delta = +3.77 yr — directionally correct)

---

## Active Items

### 1. Six Open Questions (blocks v0.3 deployment brief to Nirav)
**Status:** Awaiting Ian's decisions
**Items:**
  1. Cohort Builder default cycle selection — all vs most recent
  2. Max CSV export rows per role — internal vs researcher caps
  3. Saved cohorts visibility — private vs shareable within role
  4. Calculator placement — `/calculator` only or also embedded on main `inexion.com`
  5. Researcher invite approver — Ian-only or delegated to Anant/Na-Ri
  6. Error tracking vendor — Sentry on day one or defer
**Action:** Ian to review and decide.

### 2. Prototype Click-Through
**Status:** Built, not yet reviewed by Ian
**Action:** `streamlit run app.py` from the app folder, walk each of the five pages, flag anything that doesn't feel right.

### 3. Researcher Terms of Use
**Status:** Not drafted
**Action:** Draft click-through DUA for external researchers. Healthcare counsel review before first external invite. Target: week 4 per PRD milestone.

---

## Planned / Not Started

| Item | Owner | Milestone |
|---|---|---|
| Cloudflare R2 bucket provisioning | Nirav | Week 2 |
| Pipeline writes parquet to R2 in addition to local | Nirav | Week 2 |
| Supabase project + Google SSO + magic-link flow | Nirav | Week 2 |
| Auth proxy (FastAPI or Cloudflare Access) + Streamlit containerization | Nirav | Week 3 |
| Railway/Render staging deployment | Nirav | Week 3 |
| Audit logging to Supabase (`cohort_queries`, `saved_cohorts`, `audit_log`) | Nirav | Week 3 |
| Next.js public shell scaffolding (landing, methodology, datasets, calculator, request-access, login) | Ian | Week 4 |
| Vercel deployment + DNS for `registry.inexion.com` | Ian + Nirav | Week 4 |
| Researcher terms of use counsel review | Ian + counsel | Week 4 |
| Production cutover | Nirav + Ian | Week 4 |

---

## Scope Deferred to v0.4+

- HRS / UKB / CALERIE / GEO dataset activation (blocked on access applications — separate track)
- Saved Cohorts feature (v0.3 stretch; fine to defer)
- Cross-dataset joins
- Inferential statistics (t-tests, regressions) — researchers export and run in their own tools
- Shareable prefilled calculator URLs
- Biopharma feasibility-query product surface
- Clinic data ingestion adapter (v1.0 — blocked on Clinic A close)
- Mobile-optimized UI

---

## Key Files

| File | Description |
|---|---|
| `app.py` | Landing / home page |
| `pages/1_Dataset_Catalog.py` | Five-dataset status cards |
| `pages/2_Cohort_Builder.py` | Filter UI, live count, summary, histogram, cycle trend, CSV export |
| `pages/3_Variable_Dictionary.py` | Searchable 35-variable dictionary |
| `pages/4_Bioage_Calculator.py` | PhenoAge calculator from 9 lab values + age |
| `pages/5_Admin.py` | Data freshness, coverage, planned v0.3 additions |
| `src/config.py` | Brand colors, data paths, dataset catalog config |
| `src/data.py` | DuckDB queries (parameterized, no string-concat SQL) |
| `src/schema.py` | Variable dictionary + categorical label maps |
| `src/bioage.py` | Self-contained PhenoAge math |
| `.streamlit/config.toml` | Brand theme |
| `requirements.txt` | `streamlit`, `duckdb`, `pandas`, `plotly`, `pyarrow`, `numpy` |
| `README.md` | Run instructions, layout, data contract |
| `PRD.md` | v0.3 deployed-pilot product requirements — for Nirav review |

---

## Dependencies We Don't Control

- Nirav's availability weeks 2–4 for deployment work
- Cloudflare R2 credential provisioning
- Supabase project creation + plan tier decision
- Healthcare counsel turnaround on researcher terms (plan ~5 business days)

---

## Success Criteria for v0.3

Ships successfully when:
- Ian can log in at `registry.inexion.com/app`, run a cohort query, and export a CSV in under 60 seconds
- An invited researcher can log in the next day from a university email and see the same surface minus admin
- Nirav has a working audit log query showing every action in the current week
- Zero support tickets the first week

When 5 external researchers are actively using the app, v0.3 is validated and v0.4 begins (new datasets as access lands, saved cohorts, dataset detail pages).
