"""
HRS Explorer — 2016 Wave
Health and Retirement Study: survey data + VBS PhenoAge biological age scores.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from src.config import NAVY, GOLD, CORAL, TEAL, HRS_PUBLIC_PARQUET, HRS_VBS_PARQUET

st.set_page_config(page_title="HRS Explorer — INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding: 18px 24px; background: {NAVY}; border-radius: 8px; margin-bottom: 20px;'>
        <div style='color: {GOLD}; font-size: 12px; letter-spacing: 2px;
                    text-transform: uppercase; font-weight: 600;'>INEXION Registry</div>
        <div style='color: white; font-size: 26px; font-weight: 700; margin-top: 4px;'>
            HRS Explorer</div>
        <div style='color: #C9CBD4; font-size: 13px; margin-top: 6px;'>
            Health and Retirement Study · 2016 Wave · Survey data + Venous Blood Study PhenoAge
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_survey():
    if HRS_PUBLIC_PARQUET.exists():
        return pd.read_parquet(HRS_PUBLIC_PARQUET)
    return pd.DataFrame()

@st.cache_data
def load_vbs():
    if HRS_VBS_PARQUET.exists():
        df = pd.read_parquet(HRS_VBS_PARQUET)
        df['sex'] = df['ragender'].map({1: 'Male', 2: 'Female'})
        df['race'] = df['raracem'].map({1: 'White', 2: 'Black', 3: 'Other'})
        df['age_group'] = pd.cut(df['r13agey_b'],
            bins=[49,59,69,79,89,120], labels=['50–59','60–69','70–79','80–89','90+'])
        return df
    return pd.DataFrame()

survey = load_survey()
vbs    = load_vbs()
has_vbs = not vbs.empty

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_labels = ["Biological Age (VBS)", "Health & Function", "Demographics"] if has_vbs else ["Health & Function", "Demographics"]
tabs = st.tabs(tab_labels)
tab_offset = 0 if has_vbs else -1

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — BIOLOGICAL AGE (VBS PhenoAge)
# ══════════════════════════════════════════════════════════════════════════════
if has_vbs:
    with tabs[0]:
        # Sidebar filters
        with st.sidebar:
            st.markdown("### Filters")
            age_range = st.slider("Age range", 50, 100, (50, 90), key="vbs_age")
            sex_sel   = st.multiselect("Sex", ["Male","Female"], default=["Male","Female"], key="vbs_sex")
            race_sel  = st.multiselect("Race", ["White","Black","Other"],
                                       default=["White","Black","Other"], key="vbs_race")

        filt = vbs[
            vbs['r13agey_b'].between(*age_range) &
            vbs['sex'].isin(sex_sel) &
            vbs['race'].isin(race_sel)
        ].copy()

        # ── KPI strip ─────────────────────────────────────────────────────────
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Respondents", f"{len(filt):,}")
        c2.metric("Mean age", f"{filt['r13agey_b'].mean():.1f}")
        c3.metric("Mean PhenoAge", f"{filt['phenoage'].mean():.1f}")
        c4.metric("Mean delta", f"{filt['phenoage_delta'].mean():+.2f} yrs")
        c5.metric("% Accelerated", f"{(filt['phenoage_delta']>0).mean()*100:.0f}%")

        # ── Headline callout ──────────────────────────────────────────────────
        mean_delta = filt['phenoage_delta'].mean()
        delta_color = CORAL if mean_delta > 0 else TEAL
        st.markdown(
            f"""
            <div style='background:{NAVY}; color:white; padding:24px 28px;
                        border-radius:10px; text-align:center; margin:16px 0;'>
                <div style='color:{GOLD}; font-size:11px; letter-spacing:2px;
                            text-transform:uppercase;'>HRS 2016 · Venous Blood Study · n={len(filt):,}</div>
                <div style='font-size:48px; font-weight:800; margin-top:8px;'>
                    <span style='color:{delta_color};'>{mean_delta:+.2f}</span>
                    <span style='color:{GOLD}; font-size:24px;'> years</span>
                </div>
                <div style='font-size:16px; color:#C9CBD4; margin-top:6px;'>
                    mean biological age acceleration in Americans aged {age_range[0]}–{age_range[1]}
                </div>
                <div style='font-size:12px; color:#8B8FA8; margin-top:10px;'>
                    PhenoAge algorithm · Levine et al. 2018 · Venous blood biomarkers
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            # Delta distribution
            fig = px.histogram(filt, x='phenoage_delta', color='sex',
                color_discrete_map={'Male': NAVY, 'Female': GOLD},
                nbins=50, title='PhenoAge Delta Distribution',
                labels={'phenoage_delta': 'Biological Age Acceleration (years)'})
            fig.add_vline(x=0, line_dash='dash', line_color='gray')
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                              font_color='#1A1A2E')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Delta by age group
            age_grp = filt.groupby('age_group', observed=True)['phenoage_delta'].agg(
                ['mean','std','count']).reset_index()
            fig2 = px.bar(age_grp, x='age_group', y='mean',
                error_y='std',
                title='Mean Biological Age Acceleration by Age Group',
                labels={'age_group': 'Age Group', 'mean': 'Mean PhenoAge Delta (years)'},
                color_discrete_sequence=[CORAL])
            fig2.add_hline(y=0, line_dash='dash', line_color='gray')
            fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                               font_color='#1A1A2E')
            st.plotly_chart(fig2, use_container_width=True)

        # Chronological vs biological scatter
        sample = filt.sample(min(2000, len(filt)), random_state=42)
        fig3 = px.scatter(sample, x='r13agey_b', y='phenoage',
            color='phenoage_delta',
            color_continuous_scale=['#2E8B8B', '#FFFFFF', '#E5735B'],
            color_continuous_midpoint=0,
            title='Chronological Age vs. Biological Age (PhenoAge)',
            labels={'r13agey_b': 'Chronological Age', 'phenoage': 'Biological Age (PhenoAge)',
                    'phenoage_delta': 'Delta (years)'},
            opacity=0.6)
        fig3.add_trace(go.Scatter(
            x=[filt['r13agey_b'].min(), filt['r13agey_b'].max()],
            y=[filt['r13agey_b'].min(), filt['r13agey_b'].max()],
            mode='lines', line=dict(color='gray', dash='dash'),
            name='Biological = Chronological', showlegend=True))
        fig3.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                           font_color='#1A1A2E', height=450)
        st.plotly_chart(fig3, use_container_width=True)

        # Delta by sex and race
        col3, col4 = st.columns(2)
        with col3:
            sex_delta = filt.groupby('sex')['phenoage_delta'].mean().reset_index()
            fig4 = px.bar(sex_delta, x='sex', y='phenoage_delta',
                title='Mean Delta by Sex',
                color_discrete_sequence=[NAVY],
                labels={'sex': 'Sex', 'phenoage_delta': 'Mean Delta (years)'})
            fig4.add_hline(y=0, line_dash='dash', line_color='gray')
            fig4.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                               font_color='#1A1A2E')
            st.plotly_chart(fig4, use_container_width=True)

        with col4:
            race_delta = filt.groupby('race')['phenoage_delta'].mean().reset_index()
            fig5 = px.bar(race_delta, x='race', y='phenoage_delta',
                title='Mean Delta by Race',
                color_discrete_sequence=[TEAL],
                labels={'race': 'Race', 'phenoage_delta': 'Mean Delta (years)'})
            fig5.add_hline(y=0, line_dash='dash', line_color='gray')
            fig5.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                               font_color='#1A1A2E')
            st.plotly_chart(fig5, use_container_width=True)

        st.caption(
            "Source: HRS 2016 Venous Blood Study (restricted access). "
            "PhenoAge: Levine et al., Aging Cell 2018. "
            "Data subject to HRS Restricted Data Agreement — not for redistribution."
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — HEALTH & FUNCTION (survey data)
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1 + tab_offset]:
    if survey.empty:
        st.warning("Survey data not found. Run `build_hrs_public_parquet.py` first.")
        st.stop()

    with st.sidebar:
        age_s  = st.slider("Age range", 50, 100, (50, 90), key="surv_age")
        sex_s  = st.multiselect("Sex", ["Male","Female"], default=["Male","Female"], key="surv_sex")
        race_s = st.multiselect("Race", ["White","Black","Other"],
                                default=["White","Black","Other"], key="surv_race")

    sf = survey[
        survey['age'].between(*age_s) &
        survey['sex'].isin(sex_s) &
        survey['race'].isin(race_s)
    ].copy()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Respondents", f"{len(sf):,}")
    c2.metric("Mean age", f"{sf['age'].mean():.1f}")
    c3.metric("Mean cognitive score", f"{sf['cognitive_total'].mean():.1f} / 35")
    c4.metric("Mean conditions", f"{sf['condition_count'].mean():.1f}")

    conditions = {"Hypertension":"hypertension","Diabetes":"diabetes",
                  "Heart Disease":"heart_disease","Stroke":"stroke",
                  "Arthritis":"arthritis","Lung Disease":"lung_disease"}

    col1, col2 = st.columns(2)
    with col1:
        prev = [{"Condition":k,"Prevalence (%)":sf[v].mean()*100}
                for k,v in conditions.items()]
        fig = px.bar(pd.DataFrame(prev).sort_values("Prevalence (%)"),
                     x="Prevalence (%)", y="Condition", orientation="h",
                     title="Chronic Condition Prevalence",
                     color_discrete_sequence=[CORAL])
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                          font_color='#1A1A2E',
                          xaxis=dict(range=[0,100], ticksuffix="%"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        cog_age = sf.groupby('age_group', observed=True)['cognitive_total'].mean().reset_index()
        fig2 = px.bar(cog_age, x='age_group', y='cognitive_total',
                      title='Mean Cognitive Score by Age Group',
                      color_discrete_sequence=[TEAL],
                      labels={'age_group':'Age Group','cognitive_total':'Mean Score (0–35)'})
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig2, use_container_width=True)

    adl_col, mob_col = st.columns(2)
    with adl_col:
        fig3 = px.histogram(sf, x='adl_limitations', title='ADL Limitations (0–5)',
                            color_discrete_sequence=[NAVY],
                            labels={'adl_limitations':'ADL Limitations Count'})
        fig3.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig3, use_container_width=True)

    with mob_col:
        walk = sf.groupby('age_group', observed=True)['walking_difficulty'].mean().mul(100).reset_index()
        fig4 = px.bar(walk, x='age_group', y='walking_difficulty',
                      title='% Reporting Walking Difficulty by Age Group',
                      color_discrete_sequence=[GOLD],
                      labels={'age_group':'Age Group','walking_difficulty':'%'})
        fig4.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
                           yaxis=dict(ticksuffix='%'))
        st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DEMOGRAPHICS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2 + tab_offset]:
    if survey.empty:
        st.warning("Survey data not found.")
        st.stop()

    df_d = survey.copy()
    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(df_d, x='age', color='sex',
            color_discrete_map={'Male':NAVY,'Female':GOLD},
            nbins=30, title='Age Distribution by Sex',
            labels={'age':'Age (years)'})
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        srh_order = ["Excellent","Very Good","Good","Fair","Poor"]
        srh = df_d['self_rated_health_label'].value_counts().reindex(srh_order).reset_index()
        srh.columns = ['Rating','Count']
        fig2 = px.bar(srh, x='Rating', y='Count', title='Self-Rated Health',
                      color_discrete_sequence=[NAVY])
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig2, use_container_width=True)
