# INEXION Longevity Registry — Application PRD

**Version:** v0.3 (deployed pilot)
**Owner:** Ian Wendt (Product), Nirav Vira (Engineering)
**Status:** Draft for Nirav review
**Last updated:** 2026-04-23

---

## 1. Overview

### 1.1 Problem

INEXION has built the data science foundation for INEXION Longevity Registry (Healthspan Outcomes
Registry for Active Longevity). The pipeline runs. Parquet outputs exist. But
every analysis today requires a Python notebook and direct file access. This
limits who can use the registry, how they engage with it, and how we
demonstrate capability to investors, researchers, and biopharma partners.

The application layer converts the pipeline into a product surface that serves
three distinct audiences simultaneously.

### 1.2 Goal

Ship a deployed pilot at `registry.inexion.com` and `registry.inexion.com/app`
that supports:

- Internal INEXION team ad-hoc cohort analysis without touching code
- Invited external researchers exploring cohorts under controlled access
- Public awareness of the registry's capability, without leaking findings we
  hold for the data room

### 1.3 Non-goals for v0.3

- Clinic patient data ingestion (blocked on Clinic A close, own project)
- Full multi-omic visualization (GEO / transcriptomics need separate surface)
- A SaaS-grade tenanting model (v0.3 is single-tenant INEXION)
- A biopharma-facing feasibility query product (v0.4+, priced separately)
- Mobile-optimized UI (desktop-first — researchers and clinicians work on desktops)

---

## 2. Users & use cases

### 2.1 Internal INEXION (Ian, Na-Ri, Anant, Nirav, future data scientist)

- Pull a stat or chart for an investor email, LinkedIn post, physician conversation
- Run a cohort comparison for a new headline analysis
- Check pipeline health and data freshness
- Export a cohort slice for deeper analysis in a notebook

### 2.2 External researchers (invited only)

- Browse the dataset catalog and variable dictionary before committing to a collaboration
- Run descriptive analyses on de-identified public-source cohorts
- Export cohort-level CSVs for their own statistical tools
- Cite INEXION as a data provider in papers

### 2.3 Public (awareness audience)

- Understand what INEXION is building
- Try the biological age calculator (shareable, memorable, attributable)
- Request access as a researcher

### 2.4 Explicit out-of-scope users for v0.3

- Physicians doing clinical decision support (wait for v0.4+)
- Biopharma commercial users running feasibility queries (wait for v1.0)
- Patients looking up their own results (never — this is a registry, not a consumer app)

---

## 3. Information architecture

### 3.1 Public surface — `registry.inexion.com`

Next.js on Vercel. Static rendering where possible, minimal JS.

| Route | Purpose | Access |
|---|---|---|
| `/` | Landing. What the registry is, why it exists. No specific findings. | Public |
| `/methodology` | PhenoAge, KDM, data-source descriptions. No numbers. | Public |
| `/datasets` | Catalog: dataset names, access tiers, approximate participant counts. | Public |
| `/calculator` | Biological age calculator (PhenoAge + KDM). | Public |
| `/request-access` | Researcher invite-request form → Supabase + email notify Ian. | Public |
| `/login` | Supabase Auth entry. | Public |

### 3.2 Gated surface — `registry.inexion.com/app`

Streamlit, containerized, behind Supabase-issued JWT validated by middleware.

| Page | Purpose | Access |
|---|---|---|
| Home | Top-line registry stats, roadmap | All authenticated |
| Dataset Catalog | Full catalog with detailed status, row counts, cycles | All authenticated |
| Cohort Builder | Filters → live count → summary → chart → CSV export | All authenticated |
| Variable Dictionary | Every column with units and definitions | All authenticated |
| Biological Age Calculator | Authenticated variant (may allow batch upload later) | All authenticated |
| Saved Cohorts | Save and re-run cohort definitions | All authenticated |
| Admin | Pipeline health, audit log, user management | `internal` role only |

### 3.3 Roles

| Role | Who | Can do |
|---|---|---|
| `internal` | INEXION employees | Everything including admin |
| `researcher` | Invited external collaborators | Everything except admin |
| `public` | Unauthenticated | Public-surface pages only |

Role assignment: Google Workspace domain match (`@inexion.com`) → `internal`.
Magic-link invite accepted → `researcher`. No self-signup.

---

## 4. Functional requirements

### 4.1 Cohort Builder

**Inputs**

- Cycle selector (multi-select, all NHANES cycles)
- Dataset selector (v0.4+ — NHANES only for v0.3)
- Demographics: age range, sex multi-select, race/ethnicity multi-select, education
- Biomarker range filters: BMI, systolic BP, HbA1c, CRP, glucose, PhenoAge delta
- Advanced (collapsed by default): all other numeric variables in the dictionary

**Outputs**

- Live cohort count updated on any filter change (< 200 ms)
- Descriptive summary: n, mean age, % female, mean BMI, mean PhenoAge delta, mean biomarkers
- Histogram for a chosen variable, with brand-themed styling
- Line chart of variable trend across NHANES cycles
- Preview table of first 500 rows
- CSV export up to configurable row cap (default 10,000, hard max 200,000)

**Performance targets**

- Cohort count ≤ 200 ms on NHANES (55K rows)
- Summary ≤ 500 ms
- CSV export of 50K rows ≤ 5 s to download start

**Non-requirements**

- No inferential statistics (t-tests, regressions) in v0.3 — researchers export to do that
- No cross-dataset joins in v0.3 — each dataset is queried on its own

### 4.2 Biological Age Calculator

- 9 PhenoAge inputs + age, all in NHANES native units
- Local computation, no external API call
- Outputs: PhenoAge value, delta, 10-year mortality risk, bar chart chrono vs bio age
- Clinical caveat always present
- Shareable URL with prefilled inputs (v0.4 — deferred)

### 4.3 Variable Dictionary

- Text search across keys, labels, units, groups, descriptions
- Grouped display
- JSON download of the full dictionary for programmatic consumers

### 4.4 Dataset Catalog

- Cards for NHANES, HRS, UKB, CALERIE, GEO
- Status badge (Available / Pipeline built — access pending / Application in progress / etc.)
- Access tier, participant count, cycle range, description
- Click-through to dataset detail page (v0.4 — deferred)

### 4.5 Saved Cohorts (v0.3 stretch — ship if time allows)

- Name + save a filter set to the user's account
- Re-run to see updated count when new cycles / data arrive
- Share within role (researcher → other researchers: no. Internal → internal: yes.)

### 4.6 Admin

- Data artifact table: path, size, modified, days since refresh
- Coverage snapshot: total rows, PhenoAge coverage, KDM coverage
- Audit log search: user, action, timestamp, filter definition, row count
- User management: invite by email, revoke, role change
- Pipeline run log (links to GitHub Actions or equivalent — v0.4)

---

## 5. Data architecture

### 5.1 Storage

- Parquet files in Cloudflare R2 bucket `inexion-registry-staging`
- One prefix per dataset: `r2://inexion-registry-staging/nhanes/nhanes_with_phenoage.parquet`
- Pipeline writes R2 as an additional output alongside local file; cutover to R2-only once validated
- No egress costs from R2 to the Railway/Render container

### 5.2 Query layer

- DuckDB in-process, reading R2 parquet via `httpfs` extension
- One connection per Streamlit session, cached via `@st.cache_resource`
- All user inputs parameterized — no string-concatenated SQL
- Query timeout: 30 s. Beyond that, the cohort is too loose and the user
  needs to narrow filters.

### 5.3 Supabase Postgres

Schemas:

```sql
-- Users & auth
auth.users                      -- Supabase-managed
public.user_roles (user_id, role, created_at)
public.invites (email, role, token, invited_by, expires_at, accepted_at)

-- Usage
public.cohort_queries (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users,
    created_at timestamptz default now(),
    dataset text,
    filters jsonb,
    row_count int,
    exported boolean default false
)

public.saved_cohorts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users,
    name text,
    dataset text,
    filters jsonb,
    created_at timestamptz default now()
)

public.audit_log (
    id bigserial primary key,
    user_id uuid,
    action text,
    meta jsonb,
    created_at timestamptz default now()
)
```

### 5.4 No PHI, no PII

All v0.3 data is from de-identified public datasets. Access controls exist for
future-proofing, not because there's sensitive data today. When clinic data
enters the pipeline (v1.0), add de-identification verification and BAA flows
before exposing to this app.

---

## 6. Auth & access

### 6.1 Supabase Auth

- Google OAuth as primary login
- Email-domain rule: `@inexion.com` → auto-assign role `internal`
- Magic-link for external researchers
- Invite flow: Ian generates token via admin page → email sends magic link →
  first login creates user with role from invite

### 6.2 Middleware

- Streamlit container runs behind a tiny auth proxy (FastAPI or Cloudflare Access)
- Proxy validates Supabase JWT; rejects with 401 if absent or expired
- Streamlit reads user email + role from headers set by proxy

### 6.3 Researcher terms of use

- Click-through agreement before first Cohort Builder query
- Recorded to `public.audit_log` with timestamp + IP
- Draft prepared by me; reviewed by healthcare counsel before first external invite sent

---

## 7. Non-functional requirements

### 7.1 Performance

- Page TTFB ≤ 1 s on authenticated pages
- Cohort Builder interaction ≤ 200 ms per filter change
- Ten concurrent users supported without degradation on a single Railway 1GB container

### 7.2 Observability

- Application logs to stdout, collected by Railway / Render
- Every cohort query, saved cohort, export, and calculator run logged with
  user ID and timestamp
- Weekly usage summary emailed to Ian (via a simple scheduled job)

### 7.3 Security

- HTTPS enforced (Cloudflare edge)
- No secrets in code — Supabase service key + R2 credentials in environment
- Dependency audit on every deploy (GitHub Actions + `pip-audit`)
- No SQL injection surface (parameterized DuckDB queries only)
- Rate limit: 60 cohort queries / user / minute

### 7.4 Branding

- Navy `#0D1B3E`, Gold `#C9941A`, Dark text `#1A1A2E` — matches the research
  white paper and the LinkedIn infographic
- INEXION logo in sidebar on every page
- No stock photos, ever

---

## 8. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Public shell | Next.js (App Router) on Vercel | Matches existing marketing site; static-first; fast |
| Analytics app | Streamlit | Python-native, ships in days not weeks |
| Query engine | DuckDB | Runs parquet without a database; zero ops |
| Object storage | Cloudflare R2 | No egress fees, S3-compatible |
| Auth + accounts | Supabase | Already in use for intranet; SSO + magic-link out of the box |
| Container host | Railway (or Render) | Minimal ops; auto-deploys from GitHub; cheap |
| Domain + TLS | Cloudflare | Already at the edge; wildcard cert for `*.inexion.com` |
| CI/CD | GitHub Actions | Repo is already on GitHub |

---

## 9. Deployment

### 9.1 Environments

- `local` — developer machine, parquet on disk
- `staging` — `staging-registry.inexion.com` — R2 staging bucket, Supabase staging project
- `prod` — `registry.inexion.com` — R2 prod bucket, Supabase prod project

### 9.2 Pipeline

- Pipeline repo (`inexion-registry-pipeline`) writes parquet to R2 prod bucket
  after NHANES refresh
- App repo (`inexion-registry-app`) deploys on push to `main`
- Vercel deploys Next.js shell on push to `main` in shell repo

---

## 10. Milestones

| Week | Deliverable | Owner | Dependencies |
|---|---|---|---|
| 1 | Local prototype running against NHANES parquet | Me (Ian) | None — DONE with this prototype |
| 2 | R2 bucket provisioned, pipeline writes R2, app reads R2 | Nirav | R2 account setup |
| 2 | Supabase project + Google SSO + magic-link flow | Nirav | Supabase project creation |
| 3 | Auth proxy + Streamlit containerized + deployed to Railway staging | Nirav | Week 2 complete |
| 3 | Audit logging to Supabase | Nirav | Supabase schema migration |
| 4 | Next.js public shell live at staging domain | Me | Vercel project |
| 4 | Researcher terms of use reviewed by counsel | Ian + counsel | Draft |
| 4 | Production cutover to `registry.inexion.com` | Nirav + Ian | All above |

---

## 11. Open questions

1. **Cohort Builder defaults** — start with all cycles selected, or default to 2017–2018 only? (Recommend: all, with a one-click "last cycle only" preset.)
2. **Max export rows** — 10K default, 200K hard cap, or should the cap scale with role? (Recommend: 50K cap for researcher, 200K for internal.)
3. **Saved cohorts visibility** — private only, or shareable within role? (Recommend: private in v0.3; add sharing in v0.4 when there's demand.)
4. **Public calculator placement** — `registry.inexion.com/calculator` only, or also embed a widget on `inexion.com` marketing site? (Recommend: both; it's the most shareable feature we'll ship.)
5. **Researcher invite approval** — Ian approves each one, or delegate to Anant / Na-Ri? (Recommend: Ian-only for the first 20 invites, then review.)
6. **Observability vendor** — stdout + Supabase is fine for v0.3, but do we want Logfire / Sentry for error tracking? (Recommend: add Sentry free tier day one — it's five minutes.)

---

## 12. Dependencies we don't control

- Nirav's availability for deployment work in weeks 2–4
- Supabase project setup (fast, but requires decision on plan tier)
- Cloudflare R2 credentials
- Healthcare counsel turnaround on researcher terms (plan for 5 business days)
- NHANES refresh cadence (CDC-controlled; we refresh quarterly)

---

## 13. Success criteria

v0.3 ships successfully when:

- Ian can log in at `registry.inexion.com/app`, run a cohort query, and export a CSV in under 60 seconds
- A researcher invited today can log in tomorrow from their university email and see the same surface minus admin
- Nirav has a working audit log query showing every action this week
- Any of the above generates zero support tickets

When we have 5 external researchers actively using the app, v0.3 is validated
and v0.4 (new datasets, saved cohorts, more pages) begins.
