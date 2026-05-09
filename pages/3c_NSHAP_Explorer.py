"""
NSHAP Explorer - National Social Life, Health, and Aging Project.

Currently surfaces R1 + R2 + R3 from the public-use ICPSR releases. R3 blood
biomarkers are not in this distribution (see Outputs/NSHAP_Acquisition_Brief
for the open ask to ICPSR / NORC). R4 is restricted-only and pending IRB.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from src.config import (data_exists, NAVY, GOLD, CORAL, TEAL,
                        NSHAP_BIO_PARQUET, NSHAP_SOCIAL_PARQUET,
                        NSHAP_CODEBOOK_PARQUET)

st.set_page_config(page_title="NSHAP Explorer - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            NSHAP Explorer</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            National Social Life, Health, and Aging Project &middot; Rounds 1-3 &middot;
            adults 57-85 at baseline &middot; ICPSR public-use
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---- Categorical decoders (NSHAP convention) ----
SEX_LABELS = {1: "M", 2: "F"}
RACE_LABELS = {
    1: "Non-Hispanic White",
    2: "Non-Hispanic Black",
    3: "Hispanic",
    4: "Other",
}
EDUC_LABELS = {
    1: "Less than HS",
    2: "HS grad / GED",
    3: "Some college",
    4: "Bachelor's or above",
}

# Friendly column names for both biomarker and social parquets
COL_LABELS = {
    "nshap_id":             "NSHAP respondent ID",
    "round":                "Round",
    "wave_year":            "Wave year (midpoint)",
    "age":                  "Age (years)",
    "sex":                  "Sex",
    "race_ethnicity":       "Race / Ethnicity",
    "education":            "Education",
    "weight_adj":           "Survey weight (normalized)",
    # Anthropometry / vitals
    "bmi":                  "Body Mass Index (kg/m²)",
    "height_cm":            "Height (cm)",
    "weight_kg":            "Weight (kg)",
    "waist_cm":             "Waist circumference (cm)",
    "systolic_mean":        "Systolic BP (mmHg)",
    "diastolic_mean":       "Diastolic BP (mmHg)",
    "pulse_mean":           "Pulse (bpm)",
    # Blood biomarkers
    "hba1c_pct":            "HbA1c (%)",
    "crp_mg_l":             "CRP (mg/L)",
    "ebv_titer":            "EBV antibody titer",
    "hemoglobin":           "Hemoglobin (g/dL)",
    "a1c_whbl":             "HbA1c, whole blood (%)",
    "crp_plsm":             "CRP, plasma (mg/L)",
    "thb_whbl":             "Total hemoglobin, whole blood (g/dL)",
    "dhea_1":               "DHEA, sample 1 (saliva)",
    "dhea_2":               "DHEA, sample 2 (saliva)",
    # Social / functional
    "network_alters":       "Network size (alters named)",
    "network_close":        "Close confidants (count)",
    "network_close_knit":   "Network closeness (1-5)",
    "hearing":              "Hearing (self-rated, 1-5)",
    "smell":                "Smell test score (R1 only)",
    "walk_block":           "Walks 1 block (0=cannot)",
    "walk_room":            "Walks across room (0=cannot)",
    "walk_speed_s":         "Timed walk (seconds)",
    "moca_total":           "MoCA cognitive total (R2-R3)",
}


def _decoded(df: pd.DataFrame) -> pd.DataFrame:
    """Return a display copy with categorical codes mapped to labels and
    column names rewritten to be human-readable."""
    out = df.copy()
    if "sex" in out.columns:
        out["sex"] = out["sex"].map(SEX_LABELS).fillna(out["sex"])
    if "race_ethnicity" in out.columns:
        out["race_ethnicity"] = out["race_ethnicity"].map(RACE_LABELS).fillna("(unknown)")
    if "education" in out.columns:
        out["education"] = out["education"].map(EDUC_LABELS).fillna("(unknown)")
    out = out.rename(columns=COL_LABELS)
    return out


# ---- Loaders ----
@st.cache_data
def load_codebook():
    if not data_exists(NSHAP_CODEBOOK_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(NSHAP_CODEBOOK_PARQUET)


@st.cache_data
def load_bio():
    if not data_exists(NSHAP_BIO_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(NSHAP_BIO_PARQUET)


@st.cache_data
def load_social():
    if not data_exists(NSHAP_SOCIAL_PARQUET):
        return pd.DataFrame()
    return pd.read_parquet(NSHAP_SOCIAL_PARQUET)


bio = load_bio()
soc = load_social()
cb  = load_codebook()


if bio.empty:
    st.info("**NSHAP biomarker parquet not yet present.** Pipeline scaffolded in "
             "`inexion-registry-pipeline/build_nshap_parquet.py`.")
    st.stop()


# ---- Headline metrics ----
n_total = len(bio)
n_r1 = (bio["round"] == "NSHAP1").sum()
n_r2 = (bio["round"] == "NSHAP2").sum()
n_r3 = (bio["round"] == "NSHAP3").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total observations", f"{n_total:,}")
c2.metric("Round 1 (2005-06)", f"{n_r1:,}")
c3.metric("Round 2 (2010-11)", f"{n_r2:,}")
c4.metric("Round 3 (2015-16)", f"{n_r3:,}")
st.caption(
    "Each row is one respondent-wave observation. Round 1 baseline + Round 2 "
    "+ Round 3 stacked. The same respondent appears once per round they "
    "participated in. Weights below are the NSHAP-normalized sampling weight "
    "(~1.0 average), not body weight."
)


# ---- Tabs ----
tabs = st.tabs([
    "Overview",
    "Biomarker panel",
    "Social network + sensory",
    "Round comparison",
    "Codebook",
])


# ===== Tab 1 - Overview =====
with tabs[0]:
    st.markdown("#### Sample composition (all rounds combined)")
    bio_disp = _decoded(bio)

    c1, c2 = st.columns(2)
    with c1:
        sex_counts = bio_disp["Sex"].value_counts().reset_index()
        sex_counts.columns = ["Sex", "Count"]
        fig = px.bar(sex_counts, x="Sex", y="Count",
                      color_discrete_sequence=[NAVY],
                      title="Sex distribution")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          font_color="#1A1A2E", height=300)
        st.plotly_chart(fig, width="stretch", key="nshap_sex")
    with c2:
        race_counts = bio_disp["Race / Ethnicity"].value_counts().reset_index()
        race_counts.columns = ["Race / Ethnicity", "Count"]
        fig = px.bar(race_counts, x="Race / Ethnicity", y="Count",
                      color_discrete_sequence=[GOLD],
                      title="Race / Ethnicity distribution")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          font_color="#1A1A2E", height=300)
        st.plotly_chart(fig, width="stretch", key="nshap_race")

    c1, c2 = st.columns(2)
    with c1:
        edu_counts = bio_disp["Education"].value_counts().reset_index()
        edu_counts.columns = ["Education", "Count"]
        # Sort by canonical ordering
        edu_order = ["Less than HS", "HS grad / GED", "Some college", "Bachelor's or above"]
        edu_counts["Education"] = pd.Categorical(edu_counts["Education"],
                                                   categories=edu_order, ordered=True)
        edu_counts = edu_counts.sort_values("Education")
        fig = px.bar(edu_counts, x="Education", y="Count",
                      color_discrete_sequence=[TEAL],
                      title="Education distribution")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          font_color="#1A1A2E", height=300)
        st.plotly_chart(fig, width="stretch", key="nshap_edu")
    with c2:
        fig = px.histogram(bio_disp, x="Age (years)", nbins=30,
                            color_discrete_sequence=[CORAL],
                            title="Age distribution at interview")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          font_color="#1A1A2E", height=300)
        st.plotly_chart(fig, width="stretch", key="nshap_age")


# ===== Tab 2 - Biomarker panel =====
with tabs[1]:
    st.markdown("#### Biomarker panel by round")
    st.caption(
        "Round 1 has HbA1c, CRP, EBV from a sub-sample. Round 2 added DBS-based "
        "hemoglobin and a second wave of all R1 markers. **Round 3 blood "
        "biomarkers are NOT in the public ICPSR release** (under inquiry with "
        "ICPSR / NORC); R3 contributes anthropometry and vitals only."
    )
    biomarker_cols = [
        ("hba1c_pct",      "HbA1c (%)"),
        ("crp_mg_l",       "CRP (mg/L)"),
        ("ebv_titer",      "EBV antibody titer"),
        ("hemoglobin",     "Hemoglobin (g/dL)"),
        ("bmi",            "Body Mass Index (kg/m²)"),
        ("waist_cm",       "Waist (cm)"),
        ("systolic_mean",  "Systolic BP (mmHg)"),
        ("diastolic_mean", "Diastolic BP (mmHg)"),
    ]
    cov = []
    for col, label in biomarker_cols:
        for r, label_r in [("NSHAP1", "R1"), ("NSHAP2", "R2"), ("NSHAP3", "R3")]:
            sub = bio[bio["round"] == r]
            n = sub[col].notna().sum() if col in sub.columns else 0
            if n > 0:
                cov.append({"Marker": label, "Round": label_r,
                             "n_nonnull": int(n),
                             "mean": float(sub[col].mean()),
                             "std": float(sub[col].std())})
    cov_df = pd.DataFrame(cov)
    if not cov_df.empty:
        cov_df["mean"] = cov_df["mean"].round(2)
        cov_df["std"] = cov_df["std"].round(2)
        cov_df.columns = ["Marker", "Round", "n", "Mean", "SD"]
        st.dataframe(cov_df, width="stretch", hide_index=True)

    # Distributions for selected markers
    st.markdown("##### Marker distributions across rounds")
    show_marker = st.selectbox(
        "Marker",
        [c for c, _ in biomarker_cols],
        format_func=lambda c: dict(biomarker_cols)[c],
        key="nshap_marker_pick",
    )
    sub = bio[bio[show_marker].notna()].copy()
    if not sub.empty:
        fig = px.histogram(sub, x=show_marker, color="round",
                            nbins=40, opacity=0.6,
                            color_discrete_sequence=[NAVY, GOLD, TEAL],
                            labels={show_marker: dict(biomarker_cols)[show_marker]},
                            title=f"{dict(biomarker_cols)[show_marker]} - distribution by round")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          font_color="#1A1A2E", height=380)
        st.plotly_chart(fig, width="stretch", key=f"nshap_dist_{show_marker}")


# ===== Tab 3 - Social network + sensory =====
with tabs[2]:
    st.markdown("#### Social network + sensory + functional measures")
    st.caption(
        "NSHAP-distinctive measures not present in HRS or MIDUS. Network "
        "size = number of confidants named on the in-home roster. MoCA is "
        "the Montreal Cognitive Assessment composite (R2-R3 only)."
    )
    social_cols = [
        ("network_alters",     "Network size (alters)"),
        ("network_close",      "Close confidants"),
        ("network_close_knit", "Network closeness (1-5)"),
        ("walk_speed_s",       "Timed walk (sec)"),
        ("moca_total",         "MoCA cognitive total"),
        ("hearing",            "Hearing (self-rated)"),
        ("smell",              "Smell test (R1)"),
    ]
    cov = []
    for col, label in social_cols:
        for r, label_r in [("NSHAP1", "R1"), ("NSHAP2", "R2"), ("NSHAP3", "R3")]:
            sub = soc[soc["round"] == r]
            n = sub[col].notna().sum() if col in sub.columns else 0
            if n > 0:
                cov.append({"Measure": label, "Round": label_r,
                             "n": int(n),
                             "Mean": round(float(sub[col].mean()), 2),
                             "SD": round(float(sub[col].std()), 2)})
    cov_df = pd.DataFrame(cov)
    if not cov_df.empty:
        st.dataframe(cov_df, width="stretch", hide_index=True)

    show_measure = st.selectbox(
        "Measure",
        [c for c, _ in social_cols],
        format_func=lambda c: dict(social_cols)[c],
        key="nshap_soc_pick",
    )
    sub = soc[soc[show_measure].notna()].copy()
    if not sub.empty:
        fig = px.histogram(sub, x=show_measure, color="round",
                            nbins=30, opacity=0.6,
                            color_discrete_sequence=[NAVY, GOLD, TEAL],
                            labels={show_measure: dict(social_cols)[show_measure]},
                            title=f"{dict(social_cols)[show_measure]} - distribution by round")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          font_color="#1A1A2E", height=380)
        st.plotly_chart(fig, width="stretch", key=f"nshap_soc_{show_measure}")


# ===== Tab 4 - Round comparison =====
with tabs[3]:
    st.markdown("#### Round-by-round summary")
    st.caption(
        "Per-round n, age, and key biomarker means. Round 3 blood biomarkers "
        "appear empty - they are not in the public-use ICPSR release."
    )
    rows = []
    for r, label_r, year in [("NSHAP1", "Round 1 (2005-06)", 2006),
                              ("NSHAP2", "Round 2 (2010-11)", 2011),
                              ("NSHAP3", "Round 3 (2015-16)", 2016)]:
        sub = bio[bio["round"] == r]
        if sub.empty:
            continue
        rows.append({
            "Round": label_r,
            "n": len(sub),
            "Mean age": round(sub["age"].mean(), 1),
            "% female": round((sub["sex"] == 2).mean() * 100, 1),
            "Mean BMI": round(sub["bmi"].mean(), 2) if sub["bmi"].notna().any() else None,
            "Mean SBP": round(sub["systolic_mean"].mean(), 1) if sub["systolic_mean"].notna().any() else None,
            "Mean HbA1c (%)": round(sub["hba1c_pct"].mean(), 2) if sub["hba1c_pct"].notna().any() else None,
            "Mean CRP (mg/L)": round(sub["crp_mg_l"].mean(), 2) if sub["crp_mg_l"].notna().any() else None,
            "Mean Hb (g/dL)": round(sub["hemoglobin"].mean(), 2) if sub["hemoglobin"].notna().any() else None,
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ===== Tab 5 - Codebook =====
with tabs[4]:
    if cb.empty:
        st.warning("Codebook parquet not found.")
    else:
        st.markdown("#### Variable harmonization map across rounds")
        st.caption(
            "Per-round source variable names from ICPSR. Coverage of '3' = "
            "harmonized variable available in all 3 rounds; '2' = available "
            "in 2 rounds only (typically R2 + R3); '1' = single-round."
        )
        cb_disp = cb.copy()
        cb_disp.columns = ["Harmonized name", "R1 source",
                            "R2 source", "R3 source",
                            "# rounds", "Category"]
        st.dataframe(cb_disp, width="stretch", hide_index=True)


# Bottom: a small preview of the actual stacked biomarker frame so users
# can verify the labels look right.
with st.expander("Preview - first 50 rows of biomarker parquet (decoded)", expanded=False):
    bio_disp = _decoded(bio)
    st.dataframe(bio_disp.head(50), width="stretch")

with st.expander("Preview - first 50 rows of social/sensory parquet (decoded)", expanded=False):
    soc_disp = _decoded(soc)
    st.dataframe(soc_disp.head(50), width="stretch")
