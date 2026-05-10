"""
Clinic Explorer - INEXION longitudinal patient registry.

Surfaces the harmonized clinic-data parquets (built from Healthspan-style
EHR exports via build_clinic_parquet.py). Five data sources:

    clinic_patients      one row per patient
    clinic_visits        long format, ~70 labs per visit
    clinic_interventions long format, Rx + supplements + lifestyle
    clinic_notes         PII-scrubbed free text
    clinic_clocks        PhenoAge / Liver / Kidney age per visit

UI: cohort filter at the top + tabs for Aggregate / Labs / Interventions /
Clocks / Notes / Per-Patient drill-in.

This page is shaped around the synthetic 10K bundle but will surface real
Healthspan data the moment it lands at the same parquet paths.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import (
    NAVY, GOLD, CORAL, TEAL, LIGHT_BG,
    CLINIC_PATIENTS_PARQUET, CLINIC_VISITS_PARQUET,
    CLINIC_INTERVENTIONS_PARQUET, CLINIC_NOTES_PARQUET,
    CLINIC_CLOCKS_PARQUET,
    data_exists,
)

st.set_page_config(page_title="Clinic Explorer - INEXION Registry",
                     layout="wide")

# Header
st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;
                margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>
            INEXION Registry &middot; CLINIC LAYER</div>
        <div style='color:white;font-size:26px;font-weight:700;
                    margin-top:4px;'>Clinic Explorer</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Longitudinal patient-level registry &middot; lab panels, interventions,
            biological-age clocks, physician notes
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---- Loaders (cached) ----
@st.cache_data(show_spinner=False)
def _load_patients():
    if not data_exists(CLINIC_PATIENTS_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(CLINIC_PATIENTS_PARQUET)


@st.cache_data(show_spinner=False)
def _load_visits():
    if not data_exists(CLINIC_VISITS_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(CLINIC_VISITS_PARQUET)


@st.cache_data(show_spinner=False)
def _load_interventions():
    if not data_exists(CLINIC_INTERVENTIONS_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(CLINIC_INTERVENTIONS_PARQUET)


@st.cache_data(show_spinner=False)
def _load_clocks():
    if not data_exists(CLINIC_CLOCKS_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(CLINIC_CLOCKS_PARQUET)


@st.cache_data(show_spinner=False)
def _load_notes(max_rows: int = 50_000):
    """Notes can be large; load with a row cap by default and let the user
    request more if needed."""
    if not data_exists(CLINIC_NOTES_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(CLINIC_NOTES_PARQUET)
    return df.head(max_rows) if len(df) > max_rows else df


patients      = _load_patients()
visits        = _load_visits()
interventions = _load_interventions()
clocks        = _load_clocks()


# ---- Stub-state when no data is loaded ----
if patients.empty or visits.empty:
    st.warning(
        "Clinic parquets not on disk yet. Run from the pipeline directory:\n\n"
        "```\npython build_clinic_parquet.py --bundle <path-to-clinic-csvs> "
        "--source-clinic <source>\n```\n\n"
        "Then redeploy data with `scripts/deploy.ps1`."
    )
    st.markdown(
        f"""
        ### What this page will surface once data lands

        - **Cohort filter** &middot; clinic source, sex, age range, on-intervention
          ("show me everyone currently on rapamycin"), intervention category
        - **Aggregate metrics** &middot; patient count, visit count, intervention
          prevalence, mean PhenoAge δ across the clinic
        - **Lab distributions** &middot; histograms across the 70+ marker panel
          with cohort filtering live
        - **Interventions tab** &middot; which Rx + supplements are most prevalent,
          by category and by overlap
        - **Clocks tab** &middot; PhenoAge / Liver / Kidney age across the cohort
          and per-patient trajectories
        - **Note search** &middot; full-text search across PII-scrubbed physician
          notes
        - **Per-patient drill-in** &middot; longitudinal trajectory plots for any
          single patient, with the intervention timeline overlaid

        Data shape we're built around: 10K patients × ~4-5 visits each ×
        70 lab markers + intervention tracking + free-text notes. Matches
        the synthetic Healthspan-style bundle that informs this page.
        """
    )
    st.stop()


# ---- Cohort filter ----
st.markdown("### Cohort Filter")

with st.expander("Filters", expanded=True):
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        clinics = sorted(patients["source_clinic"].dropna().unique().tolist())
        sel_clinics = st.multiselect(
            "Source clinic", options=clinics, default=clinics,
            help="If multiple clinics are loaded, filter to one or more.",
        )
    with fc2:
        sexes = sorted(patients["sex"].dropna().unique().tolist())
        sel_sex = st.multiselect("Sex", options=sexes, default=sexes)
    with fc3:
        age_min, age_max = int(patients["age_at_first_visit"].min()), \
                            int(patients["age_at_first_visit"].max())
        sel_age = st.slider(
            "Age at first visit", min_value=age_min, max_value=age_max,
            value=(age_min, age_max),
        )
    with fc4:
        intervention_keys = sorted(
            interventions["intervention_key"].dropna().unique().tolist()
        ) if not interventions.empty else []
        sel_interventions = st.multiselect(
            "On intervention (Active status)", options=intervention_keys,
            help="Filter to patients with at least one Active intervention "
                  "matching the selected key(s). Leave blank for all patients.",
        )

# Apply filter
pat_mask = (
    patients["source_clinic"].isin(sel_clinics)
    & patients["sex"].isin(sel_sex)
    & patients["age_at_first_visit"].between(sel_age[0], sel_age[1])
)
if sel_interventions and not interventions.empty:
    active_pat = (
        interventions[
            (interventions["intervention_key"].isin(sel_interventions))
            & (interventions["status"].astype(str).str.lower() == "active")
        ]["registry_patient_id"].unique()
    )
    pat_mask &= patients["registry_patient_id"].isin(active_pat)

filtered_pat = patients[pat_mask]
filtered_pids = set(filtered_pat["registry_patient_id"])
filtered_vis = visits[visits["registry_patient_id"].isin(filtered_pids)]
filtered_int = (
    interventions[interventions["registry_patient_id"].isin(filtered_pids)]
    if not interventions.empty else interventions
)
filtered_clk = (
    clocks[clocks["registry_patient_id"].isin(filtered_pids)]
    if not clocks.empty else clocks
)


# ---- Metric strip ----
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Patients (filtered)", f"{len(filtered_pat):,}")
m2.metric("Total visits",        f"{len(filtered_vis):,}")
mean_vis = (
    filtered_pat["n_visits"].mean() if "n_visits" in filtered_pat.columns
    and len(filtered_pat) > 0 else None
)
m3.metric("Mean visits / patient",
            f"{mean_vis:.1f}" if mean_vis is not None else "—")
if not filtered_clk.empty and "phenoage_delta" in filtered_clk.columns:
    mean_pa_delta = filtered_clk["phenoage_delta"].dropna().mean()
    m4.metric("Mean PhenoAge δ",
                 f"{mean_pa_delta:+.2f} yr" if pd.notna(mean_pa_delta) else "—")
else:
    m4.metric("Mean PhenoAge δ", "—")
if not filtered_int.empty:
    active_count = (
        filtered_int[
            filtered_int["status"].astype(str).str.lower() == "active"
        ]["registry_patient_id"].nunique()
    )
    m5.metric("On any active intervention", f"{active_count:,}")
else:
    m5.metric("On any active intervention", "—")


# ---- Tabs ----
tabs = st.tabs([
    "Cohort Overview", "Lab Distributions", "Interventions",
    "Biological-Age Clocks", "Per-Patient Drill-In",
])


# =========================================================================
# TAB 1 - COHORT OVERVIEW
# =========================================================================
with tabs[0]:
    st.markdown("#### Demographics")
    c1, c2 = st.columns(2)
    with c1:
        if len(filtered_pat):
            fig = px.histogram(
                filtered_pat, x="age_at_first_visit", nbins=20,
                color="sex",
                color_discrete_map={"Male": NAVY, "Female": CORAL},
            )
            fig.update_layout(
                title="Age at first visit by sex",
                height=360, plot_bgcolor="white",
                xaxis_title="Age (years)", yaxis_title="Patient count",
                bargap=0.05,
            )
            st.plotly_chart(fig, use_container_width=True,
                              key="cohort_age_hist")
    with c2:
        if len(filtered_pat):
            sex_counts = filtered_pat["sex"].value_counts().reset_index()
            sex_counts.columns = ["sex", "n"]
            fig = px.pie(
                sex_counts, values="n", names="sex",
                color="sex",
                color_discrete_map={"Male": NAVY, "Female": CORAL},
            )
            fig.update_layout(title="Sex distribution", height=360)
            st.plotly_chart(fig, use_container_width=True,
                              key="cohort_sex_pie")

    st.markdown("#### Visit Cadence")
    if "n_visits" in filtered_pat.columns and len(filtered_pat):
        vis_counts = filtered_pat["n_visits"].value_counts().sort_index().reset_index()
        vis_counts.columns = ["n_visits", "patient_count"]
        fig = px.bar(
            vis_counts, x="n_visits", y="patient_count",
            color_discrete_sequence=[TEAL],
        )
        fig.update_layout(
            title="Patients by visit count",
            height=320, plot_bgcolor="white",
            xaxis_title="Number of visits", yaxis_title="Patient count",
        )
        st.plotly_chart(fig, use_container_width=True, key="cohort_visits")


# =========================================================================
# TAB 2 - LAB DISTRIBUTIONS
# =========================================================================
with tabs[1]:
    st.markdown("#### Lab Distributions (filtered cohort, all visits)")
    lab_cols = [c for c in filtered_vis.columns
                if c not in ("registry_patient_id", "visit_number",
                              "visit_day_offset", "age_at_visit", "sex",
                              "fasting_bool")
                and pd.api.types.is_numeric_dtype(filtered_vis[c])]
    if not lab_cols:
        st.info("No numeric lab columns in the filtered visits.")
    else:
        default_lab = next(
            (c for c in ["hba1c_pct", "crp_cardiac_mg_L", "glucose_mg_dL",
                          "hdl_cholesterol_mg_dL", "albumin_g_dL"]
             if c in lab_cols), lab_cols[0]
        )
        sel_lab = st.selectbox(
            "Marker", options=lab_cols,
            index=lab_cols.index(default_lab) if default_lab in lab_cols else 0,
        )
        series = pd.to_numeric(filtered_vis[sel_lab], errors="coerce").dropna()
        if len(series) > 0:
            c1, c2 = st.columns(2)
            with c1:
                fig = px.histogram(
                    series, nbins=40,
                    color_discrete_sequence=[NAVY],
                )
                fig.update_layout(
                    title=f"{sel_lab} - distribution across {len(series):,} visits",
                    height=380, plot_bgcolor="white",
                    xaxis_title=sel_lab, yaxis_title="Visit count",
                    bargap=0.05, showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True, key="lab_hist")
            with c2:
                # Vs age scatter
                df_scat = filtered_vis[["age_at_visit", sel_lab]].dropna()
                fig = px.scatter(
                    df_scat, x="age_at_visit", y=sel_lab,
                    opacity=0.4,
                    color_discrete_sequence=[TEAL],
                )
                fig.update_layout(
                    title=f"{sel_lab} vs age at visit",
                    height=380, plot_bgcolor="white",
                )
                st.plotly_chart(fig, use_container_width=True, key="lab_scatter")
            st.caption(
                f"n={len(series):,} visits  ·  "
                f"mean={series.mean():.2f}  ·  "
                f"median={series.median():.2f}  ·  "
                f"IQR=[{series.quantile(.25):.2f}, {series.quantile(.75):.2f}]"
            )


# =========================================================================
# TAB 3 - INTERVENTIONS
# =========================================================================
with tabs[2]:
    if filtered_int.empty:
        st.info("No interventions in the filtered cohort.")
    else:
        active = filtered_int[
            filtered_int["status"].astype(str).str.lower() == "active"
        ]

        # Detect whether harmonized columns are present (set by Phase D
        # pipeline). Falls back gracefully to the legacy view when the
        # parquet hasn't been rebuilt yet.
        _harm_cols = ["therapeutic_class", "mechanism_class",
                      "atc_code", "rxnorm_cui", "snomed_id", "inexion_code"]
        _has_taxonomy = all(c in active.columns for c in _harm_cols[:2])

        # ---- Grouping selector ----
        if _has_taxonomy:
            group_label_map = {
                "Therapeutic class (broad)": "therapeutic_class",
                "Mechanism class (specific)": "mechanism_class",
                "Raw clinic category":         "category",
                "Individual intervention":     "intervention",
            }
            choice = st.radio(
                "Group by",
                list(group_label_map.keys()),
                horizontal=True,
                key="int_group_by",
            )
            group_col = group_label_map[choice]
        else:
            st.warning(
                "Intervention taxonomy not yet present in the parquet. "
                "Re-run `build_clinic_parquet.py` to harmonize interventions "
                "against the INEXION taxonomy (therapeutic_class, "
                "mechanism_class, ATC codes, etc.)."
            )
            group_col = "intervention"

        # ---- Prevalence bar (current grouping) ----
        st.markdown(f"#### Prevalence by {group_col.replace('_', ' ')}")
        prev = (
            active.groupby(group_col)["registry_patient_id"]
                  .nunique().sort_values(ascending=True)
        )
        if len(prev):
            top = prev.tail(30)
            fig = px.bar(
                x=top.values, y=top.index, orientation="h",
                color_discrete_sequence=[GOLD],
            )
            fig.update_layout(
                title=(f"Active interventions by {group_col.replace('_', ' ')}"
                         f" - {len(top)} groups"),
                height=560, plot_bgcolor="white",
                xaxis_title="Patients (active)", yaxis_title="",
                margin=dict(l=240),
            )
            st.plotly_chart(fig, use_container_width=True, key="int_prev")

        # ---- Drill-in: when grouped by therapeutic class, show
        #      mechanism breakdown within selected class.
        if _has_taxonomy and group_col == "therapeutic_class":
            st.markdown("#### Mechanism breakdown within therapeutic class")
            classes = sorted(active["therapeutic_class"].dropna().unique())
            if classes:
                sel = st.selectbox(
                    "Therapeutic class",
                    classes,
                    key="int_class_drill",
                )
                sub = active[active["therapeutic_class"] == sel]
                mech_prev = (
                    sub.groupby("mechanism_class")["registry_patient_id"]
                       .nunique().sort_values(ascending=True)
                )
                if len(mech_prev):
                    fig = px.bar(
                        x=mech_prev.values, y=mech_prev.index, orientation="h",
                        color_discrete_sequence=[TEAL],
                    )
                    fig.update_layout(
                        title=f"{sel} - mechanisms by patient count",
                        height=max(240, 40 * len(mech_prev) + 100),
                        plot_bgcolor="white",
                        xaxis_title="Patients (active)", yaxis_title="",
                        margin=dict(l=240),
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                       key="int_mech_drill")

                # Member interventions in this class
                members = (
                    sub.groupby("intervention")["registry_patient_id"]
                       .nunique().sort_values(ascending=False)
                       .reset_index()
                       .rename(columns={"registry_patient_id": "patients"})
                )
                st.dataframe(
                    members, use_container_width=True, hide_index=True,
                )

        # ---- Code coverage panel ----
        if _has_taxonomy:
            st.markdown("#### Standard-code coverage")
            n_rows = len(active)
            cov_rows = []
            for col, label in [
                ("atc_code",    "WHO ATC"),
                ("rxnorm_cui",  "NIH RxNorm CUI"),
                ("snomed_id",   "SNOMED CT"),
                ("inexion_code", "INEXION namespace"),
            ]:
                if col in active.columns:
                    n_nn = active[col].notna().sum()
                    pct  = (100.0 * n_nn / n_rows) if n_rows else 0.0
                    cov_rows.append({
                        "Code system":          label,
                        "Intervention rows":    f"{n_nn:,}",
                        "% of active rows":     f"{pct:.1f}%",
                    })
            if cov_rows:
                st.dataframe(
                    pd.DataFrame(cov_rows),
                    use_container_width=True, hide_index=True,
                )
            st.caption(
                "RxNorm / SNOMED are stubbed to null in v1 of the "
                "taxonomy; backfill via RxNav API is a future ticket. "
                "INEXION namespace codes are always populated."
            )


# =========================================================================
# TAB 4 - BIOLOGICAL-AGE CLOCKS
# =========================================================================
with tabs[3]:
    if filtered_clk.empty:
        st.info(
            "Clinic clocks parquet not on disk. Re-run build_clinic_parquet.py "
            "without --no-clocks to produce it."
        )
    else:
        st.markdown("#### PhenoAge δ Distribution")
        delta_series = filtered_clk["phenoage_delta"].dropna()
        if len(delta_series) > 0:
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean δ", f"{delta_series.mean():+.2f} yr")
            c2.metric("Median δ", f"{delta_series.median():+.2f} yr")
            c3.metric("% biologically older",
                         f"{(delta_series > 0).mean() * 100:.1f}%")

            fig = px.histogram(
                delta_series, nbins=40,
                color_discrete_sequence=[NAVY],
            )
            fig.add_vline(x=0, line_dash="dash", line_color=GOLD,
                            annotation_text="Chrono = Bio",
                            annotation_position="top right")
            fig.update_layout(
                title="PhenoAge δ (years older / younger than chrono age)",
                height=380, plot_bgcolor="white",
                xaxis_title="PhenoAge − chronological age",
                yaxis_title="Visit count",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, key="pa_delta_hist")

        st.markdown("#### PhenoAge vs Chronological Age")
        df_scat = filtered_clk[["age_at_visit", "phenoage"]].dropna()
        if len(df_scat) > 0:
            fig = px.scatter(
                df_scat, x="age_at_visit", y="phenoage",
                opacity=0.4, color_discrete_sequence=[TEAL],
            )
            fig.add_shape(type="line", line=dict(color=GOLD, dash="dash",
                                                   width=2),
                            x0=df_scat["age_at_visit"].min(),
                            y0=df_scat["age_at_visit"].min(),
                            x1=df_scat["age_at_visit"].max(),
                            y1=df_scat["age_at_visit"].max())
            fig.update_layout(
                title="PhenoAge vs chronological age (gold line = identity)",
                height=400, plot_bgcolor="white",
            )
            st.plotly_chart(fig, use_container_width=True, key="pa_scatter")

        # Liver + Kidney ages metrics
        st.markdown("#### Organ-Age Clocks")
        oc1, oc2 = st.columns(2)
        if "liver_age_delta" in filtered_clk.columns:
            lv = filtered_clk["liver_age_delta"].dropna()
            with oc1:
                if len(lv) > 0:
                    st.metric("Liver age δ (mean)", f"{lv.mean():+.2f} yr")
                    fig = px.histogram(lv, nbins=30,
                                          color_discrete_sequence=[CORAL])
                    fig.update_layout(
                        title="Liver age − chrono age",
                        height=300, plot_bgcolor="white", bargap=0.05,
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                      key="liver_hist")
        if "kidney_age_delta" in filtered_clk.columns:
            kd = filtered_clk["kidney_age_delta"].dropna()
            with oc2:
                if len(kd) > 0:
                    st.metric("Kidney age δ (mean)", f"{kd.mean():+.2f} yr")
                    fig = px.histogram(kd, nbins=30,
                                          color_discrete_sequence=[TEAL])
                    fig.update_layout(
                        title="Kidney age − chrono age",
                        height=300, plot_bgcolor="white", bargap=0.05,
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                      key="kidney_hist")


# =========================================================================
# TAB 5 - PER-PATIENT DRILL-IN
# =========================================================================
with tabs[4]:
    st.markdown("#### Per-Patient Trajectory")
    if len(filtered_pat) == 0:
        st.info("Filtered cohort is empty.")
    else:
        sel_pat = st.selectbox(
            "Choose a patient (registry_patient_id)",
            options=filtered_pat["registry_patient_id"].tolist()[:500],
            help="First 500 patients from the filtered cohort.",
        )
        if sel_pat:
            pat_row = filtered_pat[filtered_pat["registry_patient_id"] == sel_pat].iloc[0]
            pat_vis = filtered_vis[filtered_vis["registry_patient_id"] == sel_pat] \
                        .sort_values("visit_number")
            pat_clk = filtered_clk[filtered_clk["registry_patient_id"] == sel_pat] \
                        .sort_values("visit_number") if not filtered_clk.empty else pd.DataFrame()
            pat_int = filtered_int[filtered_int["registry_patient_id"] == sel_pat] \
                        if not filtered_int.empty else pd.DataFrame()

            pc1, pc2, pc3 = st.columns(3)
            pc1.metric("Visits", len(pat_vis))
            pc2.metric("Age at first visit",
                          f"{int(pat_row['age_at_first_visit'])}")
            pc3.metric("Sex", pat_row["sex"])

            # Clock trajectories
            if not pat_clk.empty:
                fig = go.Figure()
                if pat_clk["phenoage"].notna().any():
                    fig.add_trace(go.Scatter(
                        x=pat_clk["visit_number"], y=pat_clk["phenoage"],
                        name="PhenoAge", mode="lines+markers",
                        line=dict(color=NAVY, width=2),
                    ))
                if pat_clk["liver_age"].notna().any():
                    fig.add_trace(go.Scatter(
                        x=pat_clk["visit_number"], y=pat_clk["liver_age"],
                        name="Liver age", mode="lines+markers",
                        line=dict(color=CORAL, width=2),
                    ))
                if pat_clk["kidney_age"].notna().any():
                    fig.add_trace(go.Scatter(
                        x=pat_clk["visit_number"], y=pat_clk["kidney_age"],
                        name="Kidney age", mode="lines+markers",
                        line=dict(color=TEAL, width=2),
                    ))
                if pat_clk["age_at_visit"].notna().any():
                    fig.add_trace(go.Scatter(
                        x=pat_clk["visit_number"], y=pat_clk["age_at_visit"],
                        name="Chronological", mode="lines",
                        line=dict(color=GOLD, dash="dash", width=2),
                    ))
                fig.update_layout(
                    title=f"Biological-age trajectory for {sel_pat[:8]}...",
                    height=400, plot_bgcolor="white",
                    xaxis_title="Visit number", yaxis_title="Age (years)",
                )
                st.plotly_chart(fig, use_container_width=True, key="pat_clocks")

            # Active interventions
            if not pat_int.empty:
                st.markdown("**Active interventions:**")
                active_pat = pat_int[
                    pat_int["status"].astype(str).str.lower() == "active"
                ]
                if len(active_pat) > 0:
                    st.dataframe(
                        active_pat[["intervention", "category", "dose",
                                     "start_day_offset", "status"]],
                        use_container_width=True, hide_index=True,
                    )
                else:
                    st.caption("No active interventions on record.")

            # Visit-level labs for this patient
            with st.expander(
                f"Lab values across {len(pat_vis)} visits", expanded=False
            ):
                st.dataframe(pat_vis, use_container_width=True, height=400)


st.markdown("---")
st.caption(
    "Clinic data shape: ~10K patients × 4-5 visits × 70 labs + intervention "
    "tracking + free-text notes. All patient IDs are SHA-256 hashed; all "
    "dates are per-patient relative day offsets after a deterministic "
    "date-shift. Free-text notes are PII-scrubbed (regex stub for v1; "
    "production wires Claude / AWS Comprehend Medical). The PhenoAge / Liver "
    "age / Kidney age columns in clinic_clocks.parquet apply the registry's "
    "existing NHANES-trained clocks to every clinic visit, so a clinic "
    "patient's longitudinal biological-age trajectory is computable "
    "immediately on ingest."
)
