"""
Home - INEXION Longevity Registry landing page content.

Routed from app.py via st.navigation. Reads from src.config and the data
parquets to populate registry-wide metrics + dataset descriptions.
"""
import streamlit as st
import pandas as pd
from src.config import (data_exists,
    APP_VERSION, NAVY, GOLD, TEAL, CORAL,
    NHANES_PARQUET, HRS_VBS_PARQUET, HRS_DBS_PARQUET,
    HRS_EPIGEN_PARQUET, HRS_POA_PARQUET, HRS_PUBLIC_PARQUET,
    MIDUS_BIO_PARQUET, MIDUS_COG_PARQUET,
    NSHAP_BIO_PARQUET, NSHAP_SOCIAL_PARQUET,
    GEO_CATALOG_PARQUET,
    CLINIC_PATIENTS_PARQUET, CLINIC_VISITS_PARQUET,
    CLINIC_INTERVENTIONS_PARQUET,
)

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:24px;'>
        <div style='color:{GOLD};font-size:13px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION</div>
        <div style='color:white;font-size:28px;font-weight:700;margin-top:4px;'>
            Longevity Data Registry</div>
        <div style='color:#C9CBD4;font-size:14px;margin-top:4px;'>
            INEXION Longevity Registry &nbsp;-&nbsp; v{APP_VERSION}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def get_registry_stats():
    stats = {}

    if data_exists(NHANES_PARQUET):
        df = pd.read_parquet(NHANES_PARQUET, columns=['seqn'])
        stats['nhanes_n'] = len(df)

    if data_exists(HRS_VBS_PARQUET):
        df = pd.read_parquet(HRS_VBS_PARQUET, columns=['hhidpn'])
        stats['hrs_vbs_n'] = len(df)

    if data_exists(HRS_DBS_PARQUET):
        df = pd.read_parquet(HRS_DBS_PARQUET, columns=['hhidpn'])
        stats['hrs_dbs_n'] = df['hhidpn'].nunique()
        stats['hrs_dbs_obs'] = len(df)

    if data_exists(HRS_EPIGEN_PARQUET):
        df = pd.read_parquet(HRS_EPIGEN_PARQUET, columns=['hhidpn'])
        stats['hrs_epi_n'] = len(df)

    if data_exists(HRS_POA_PARQUET):
        df = pd.read_parquet(HRS_POA_PARQUET, columns=['hhidpn'])
        stats['hrs_poa_n'] = len(df)

    if data_exists(MIDUS_BIO_PARQUET):
        df = pd.read_parquet(MIDUS_BIO_PARQUET, columns=['midus_id'])
        stats['midus_bio_n'] = len(df)

    if data_exists(MIDUS_COG_PARQUET):
        df = pd.read_parquet(MIDUS_COG_PARQUET, columns=['midus_id'])
        stats['midus_cog_n'] = len(df)

    if data_exists(NSHAP_BIO_PARQUET):
        df = pd.read_parquet(NSHAP_BIO_PARQUET, columns=['nshap_id'])
        stats['nshap_bio_n'] = len(df)

    # GEO molecular-aging reference catalog (15 transcriptomics datasets)
    if data_exists(GEO_CATALOG_PARQUET):
        try:
            df = pd.read_parquet(GEO_CATALOG_PARQUET)
            stats['geo_datasets']     = len(df)
            stats['geo_samples']      = int(df['n_samples'].sum())
            stats['geo_with_expr']    = int(df.get('has_expression', pd.Series(dtype=bool)).sum())
        except Exception:
            pass

    # INEXION clinic layer (first-party longitudinal patient registry)
    if data_exists(CLINIC_PATIENTS_PARQUET):
        try:
            cp = pd.read_parquet(CLINIC_PATIENTS_PARQUET,
                                  columns=['registry_patient_id'])
            stats['clinic_patients'] = len(cp)
        except Exception:
            pass
    if data_exists(CLINIC_VISITS_PARQUET):
        try:
            cv = pd.read_parquet(CLINIC_VISITS_PARQUET,
                                  columns=['registry_patient_id'])
            stats['clinic_visits'] = len(cv)
        except Exception:
            pass
    if data_exists(CLINIC_INTERVENTIONS_PARQUET):
        try:
            ci = pd.read_parquet(CLINIC_INTERVENTIONS_PARQUET,
                                  columns=['registry_patient_id'])
            stats['clinic_interventions'] = len(ci)
        except Exception:
            pass

    stats['total_observations'] = (
        stats.get('nhanes_n', 0) +
        stats.get('hrs_vbs_n', 0) +
        stats.get('hrs_dbs_obs', 0) +
        stats.get('hrs_epi_n', 0) +
        stats.get('hrs_poa_n', 0) +
        stats.get('midus_bio_n', 0) +
        stats.get('nshap_bio_n', 0) +
        stats.get('geo_samples', 0) +
        stats.get('clinic_visits', 0)
    )
    stats['datasets_loaded'] = sum(
        1 for k in ['nhanes_n','hrs_vbs_n','hrs_dbs_n','hrs_epi_n','hrs_poa_n',
                    'midus_bio_n','nshap_bio_n','geo_datasets',
                    'clinic_patients']
        if k in stats
    )
    return stats


try:
    s = get_registry_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Datasets loaded", s.get('datasets_loaded', 0))
    c2.metric("Total observations", f"{s.get('total_observations',0):,}")
    c3.metric("NHANES", f"{s.get('nhanes_n',0):,}")
    c4.metric("HRS VBS", f"{s.get('hrs_vbs_n',0):,}")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("HRS DBS respondents", f"{s.get('hrs_dbs_n',0):,}")
    c6.metric("HRS DunedinPACE", f"{s.get('hrs_poa_n',0):,}")
    c7.metric("MIDUS biomarker", f"{s.get('midus_bio_n',0):,}")
    c8.metric("NSHAP biomarker", f"{s.get('nshap_bio_n',0):,}")
    c9, c10, c11, c12 = st.columns(4)
    c9.metric(
        "GEO catalog datasets",
        f"{s.get('geo_datasets', 0)} / 15",
        help="Curated molecular-aging transcriptomics reference layer.",
    )
    c10.metric(
        "GEO catalog samples",
        f"{s.get('geo_samples', 0):,}",
        help="Total samples across all loaded GEO accessions.",
    )
    c11.metric(
        "GEO with expression",
        f"{s.get('geo_with_expr', 0)} / {s.get('geo_datasets', 0)}",
        help="Datasets with analysis-ready expression matrices on disk.",
    )
    c12.metric(
        "INEXION clinic patients",
        f"{s.get('clinic_patients', 0):,}",
        help=(
            "First-party longitudinal patient registry. Synthetic seed "
            "today; Healthspan + partner clinic bundles land here."
        ),
    )
    c13, c14, _, _ = st.columns(4)
    c13.metric(
        "Clinic visits",
        f"{s.get('clinic_visits', 0):,}",
        help="Total visit-level observations across all clinic patients.",
    )
    c14.metric(
        "Clinic intervention rows",
        f"{s.get('clinic_interventions', 0):,}",
        help=(
            "Active intervention records, harmonized to a 44-entry "
            "longevity taxonomy (16 therapeutic classes, ATC codes "
            "where standardized)."
        ),
    )
except Exception as e:
    st.warning(f"Could not load registry stats: {e}")

st.markdown("---")
st.markdown("### What's in the registry")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        f"""
        <div style='background:#F2F4F8;border-left:4px solid {GOLD};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>
                INEXION Clinic Layer <span style='color:{GOLD};
                font-size:11px;font-weight:600;letter-spacing:1px;
                text-transform:uppercase;margin-left:6px;'>First-party</span>
            </div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                10,000 patients - ~4.5 visits/patient - 70-marker lab panel - PhenoAge + Liver + Kidney clocks per visit<br>
                Intervention harmonization across a 44-entry longevity taxonomy (NAD pathway, mTOR modulation, senolytic, peptide therapy, hormone replacement) with ATC codes and INEXION namespace fallback.<br>
                <strong>Status:</strong> synthetic seed deployed; Healthspan + partner clinic bundles absorb cleanly via the same pipeline.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {NAVY};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>NHANES 2001-2018</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                44,898 adults - 9 cycles - PhenoAge + KDM computed<br>
                <strong>Finding:</strong> U.S. adults aged 40-60 are aging 6.8 years faster biologically than in 2009.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {GOLD};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS 2016 Venous Blood Study</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                9,567 adults 50+ - PhenoAge from real venous blood biomarkers<br>
                <strong>Finding:</strong> Highest biological age quintile is nearly 2x as likely to be cognitively impaired (27.9% vs 14.2%).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {TEAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS DBS Longitudinal (2006-2016)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                22,378 unique respondents - 6 waves - HbA1c, CRP, cholesterol, HDL, cystatin-C<br>
                Enables longitudinal biomarker trajectory analysis.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {NAVY};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>MIDUS (M2 + Refresher 1 + M3, 2004-2022)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                2,865 biomarker observations across 3 waves + 3,291 M3 cognitive (BTACT) - KDM bioage with within-MIDUS reference parameters<br>
                Distinctive for the registry: 9-marker inflammation panel (CRP, IL-6/8/10, TNF-alpha, fibrinogen, sICAM, sE-selectin, sUPAR), neuroendocrine (DHEA-S, IGF-1, urinary cortisol/catecholamines), bone turnover.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div style='background:#F2F4F8;border-left:4px solid {TEAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS Epigenetic Clocks</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                4,018 respondents - GrimAge2 + DunedinPACE (methylation-based)<br>
                Enables direct comparison of clinical biomarker vs. epigenetic clock approaches.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {CORAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>HRS Pace of Aging (DunedinPACE)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                13,358 respondents - Balachandran et al. 2025, Nature Aging<br>
                Mean DunedinPACE: 1.49 years per calendar year (population average = 1.0).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {NAVY};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>NSHAP (Rounds 1-3, 2005-2016)</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                10,578 observations stacked across 3 rounds (n~3,000-4,400 per wave) - adults 57-85<br>
                Distinctive for the registry: in-home social-network roster, sensory measures (smell / hearing / peak flow), salivary cortisol + DHEA, MoCA cognition. Round 1+2 have DBS biomarkers (HbA1c, CRP, EBV, hemoglobin); Round 3 biomeasures pending separate ICPSR release. Round 4 restricted-only.
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {GOLD};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>BRFSS 2024 - Market Intelligence</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                457,670 U.S. adults - State and metro-level longevity market scoring<br>
                Identifies where INEXION-aligned consumer demand is strongest (DC corridor, MA, NH, UT, CO).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid {TEAL};
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>GEO Molecular Aging Reference</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                15 curated transcriptomics datasets - ~2,500 samples - blood / muscle /
                fibroblast / multi-tissue<br>
                Covers blood-aging atlas (Allen Institute, n=1,120), metformin RCT
                (GSE157585), transcriptomic clock training (GSE193141), CD8 senescence
                (GSE310729), SASP signatures, intervention response. 12 of 15
                accessions with analysis-ready expression matrices recoverable
                (GEO suppl + Zenodo + Allen Atlas).
            </div>
        </div>
        <div style='background:#F2F4F8;border-left:4px solid #6B6B8D;
                    padding:16px 20px;border-radius:4px;margin-bottom:12px;'>
            <div style='font-weight:700;color:{NAVY};font-size:16px;'>Incoming</div>
            <div style='color:#4A4A4A;font-size:14px;margin-top:6px;'>
                UK Biobank (application in progress) - All of Us NIH (Anant, Tier 2 pending) -
                MIDUS CMS-linked restricted tier (Anant) - NSHAP R3 biomeasures release (open ask to ICPSR/NORC) -
                AgelessRx + Healthspan (DUA in review)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown("### What you can do")

left, right = st.columns(2)
with left:
    st.markdown(
        "**Clinic Explorer** - INEXION's first-party longitudinal registry. "
        "Cohort filter (source clinic, sex, age, on-intervention) + 5 tabs: "
        "Cohort Overview, Lab Distributions across the 70-marker panel, "
        "Interventions grouped by therapeutic / mechanism / category / individual "
        "with code-coverage panel, Biological-Age Clocks (PhenoAge δ + Liver "
        "+ Kidney), and Per-Patient Drill-In (trajectory + intervention timeline).\n\n"
        "**NHANES Explorer** - filter the 44,898-person NHANES cohort by age, sex, "
        "race, BMI, and biomarker values. See live counts, descriptive summaries, "
        "cycle trends, and export cohort slices as CSV.\n\n"
        "**HRS Explorer** - explore venous blood PhenoAge scores, epigenetic clocks, "
        "longitudinal DBS biomarker trends (2006-2016), cognitive outcomes, "
        "and functional status across five tabs.\n\n"
        "**MIDUS Explorer** - inflammation-panel-first cohort view across 3 biomarker "
        "waves (2004-2022). Tabs: Overview, Inflammation Panel, Cardiometabolic, "
        "Neuroendocrine, Wave Comparison, Cognition (M3 BTACT).\n\n"
        "**NSHAP Explorer** - 10,578 observations across 3 rounds (2005-2016). "
        "DBS biomarkers (R1+R2), in-home social network roster, sensory + functional "
        "measures, MoCA cognition.\n\n"
        "**GEO Explorer** - the curated molecular-aging transcriptomics catalog. "
        "Catalog overview + per-dataset drill-in: series info, sample metadata, "
        "demographic distributions, expression matrix preview where available."
    )
with right:
    st.markdown(
        "**Patient Analysis** - upload a PDF lab report once (or enter values manually) "
        "and explore the same patient across six tabs: PhenoAge biological age + "
        "10-year mortality risk, normative percentile vs. the U.S. population for their "
        "age-sex-race group, PhenoAge intervention simulator, plus Metabolic / Liver / "
        "Kidney organ-age clocks (Phase 4 NHANES-trained).\n\n"
        "**Validation Dashboard** - every clock the registry exposes tested against "
        "linked mortality from its source cohort. Cox proportional hazards, "
        "Kaplan-Meier survival curves, and concordance-index head-to-head between "
        "PhenoAge, KDM, GrimAge2, and DunedinPACE.\n\n"
        "**Organ Ages + Methylation Clocks** - per-system biological-age clocks "
        "(Inflammation, Liver, Kidney, Metabolic) and the methylation v0 page surfacing "
        "GrimAge2 + DunedinPACE in HRS.\n\n"
        "**Pathway Decomposition** - reproduces the GSE242202 muscle-aging "
        "decomposition: primary aging vs chronic inflammation vs disuse / atrophy "
        "scored from canonical gene panels and ranked by R² vs chronological age.\n\n"
        "**Research Workbench** - no-code hypothesis testing across NHANES, HRS, "
        "HRS DBS, MIDUS, and NSHAP. OLS, Cox PH, logistic, mixed-effects, and GAM "
        "with BH-FDR session log."
    )

st.markdown("---")
st.caption(
    "All source data is de-identified. No PHI is present. "
    "NHANES: CDC public-use files. HRS: University of Michigan / NIA restricted access under RDA. "
    "MIDUS: ICPSR public-use files (CMS-linked restricted tier in progress). "
    "NSHAP: ICPSR public-use Rounds 1-3 (R3 biomeasures + R4 pending). "
    "Prototype build - auth, audit logging, and remote object storage added in deployment phase."
)
