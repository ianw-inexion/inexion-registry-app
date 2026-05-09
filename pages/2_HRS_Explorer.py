"""
HRS Explorer - Full restricted + public dataset suite.

Tabs:
  1. Biological Age (VBS PhenoAge)
  2. Clock Comparison (PhenoAge vs GrimAge2 vs DunedinPACE)
  3. Longitudinal Biomarkers (DBS 2006-2016)
  4. Health & Function (survey)
  5. Demographics
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from src.config import (data_exists, NAVY, GOLD, CORAL, TEAL,
                        HRS_PUBLIC_PARQUET, HRS_VBS_PARQUET,
                        HRS_DBS_PARQUET, HRS_EPIGEN_PARQUET, HRS_POA_PARQUET)
from src.stats import weighted_mean, weighted_pct, effective_n

st.set_page_config(page_title="HRS Explorer - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            HRS Explorer</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Health and Retirement Study - 2016 Wave - VBS - DBS 2006-2016 - Epigenetic Clocks - DunedinPACE
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

@st.cache_data
def load_survey():
    return pd.read_parquet(HRS_PUBLIC_PARQUET) if data_exists(HRS_PUBLIC_PARQUET) else pd.DataFrame()

@st.cache_data
def load_vbs():
    if not data_exists(HRS_VBS_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(HRS_VBS_PARQUET)
    df['sex']  = df['ragender'].map({1:'Male', 2:'Female'})
    df['race'] = df['raracem'].map({1:'White', 2:'Black', 3:'Other'})
    df['age_group'] = pd.cut(df['r13agey_b'],
        bins=[49,59,69,79,89,120], labels=['50-59','60-69','70-79','80-89','90+'])
    if data_exists(HRS_PUBLIC_PARQUET):
        pub = pd.read_parquet(HRS_PUBLIC_PARQUET)[['respondent_id','survey_weight']]
        pub['hhidpn'] = pd.to_numeric(pub['respondent_id'], errors='coerce')
        df['hhidpn'] = pd.to_numeric(df['hhidpn'], errors='coerce')
        df = df.merge(pub[['hhidpn','survey_weight']], on='hhidpn', how='left')
    return df

@st.cache_data
def load_dbs():
    return pd.read_parquet(HRS_DBS_PARQUET) if data_exists(HRS_DBS_PARQUET) else pd.DataFrame()

@st.cache_data
def load_clocks():
    if not data_exists(HRS_EPIGEN_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(HRS_EPIGEN_PARQUET)
    return df

@st.cache_data
def load_poa():
    if not data_exists(HRS_POA_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(HRS_POA_PARQUET)
    df['hhidpn'] = pd.to_numeric(df['hhidpn'], errors='coerce')
    return df

survey  = load_survey()
vbs     = load_vbs()
dbs     = load_dbs()
clocks  = load_clocks()
poa     = load_poa()
has_vbs    = not vbs.empty
has_dbs    = not dbs.empty
has_clocks = not clocks.empty
has_poa    = not poa.empty

tabs = st.tabs([
    "Biological Age (VBS)",
    "Clock Comparison",
    "Longitudinal Biomarkers",
    "Health & Function",
    "Demographics",
])

# TAB 1 - BIOLOGICAL AGE (VBS PhenoAge)
with tabs[0]:
    if not has_vbs:
        st.warning("VBS PhenoAge data not found. Run the VBS pipeline first.")
        st.stop()

    with st.sidebar:
        st.markdown("### Filters")
        age_range = st.slider("Age range", 50, 100, (50, 90), key="vbs_age")
        sex_sel   = st.multiselect("Sex", ["Male","Female"], default=["Male","Female"], key="vbs_sex")
        race_sel  = st.multiselect("Race", ["White","Black","Other"],
                                   default=["White","Black","Other"], key="vbs_race")
        st.markdown("---")
        use_weights = st.toggle(
            "Survey-weighted",
            value=True,
            key="vbs_weighted",
            help="Use HRS R13WTRESP respondent weight from the RAND HRS public file."
        )

    filt = vbs[
        vbs['r13agey_b'].between(*age_range) &
        vbs['sex'].isin(sex_sel) &
        vbs['race'].isin(race_sel)
    ].copy()

    w = filt['survey_weight'].to_numpy() if (use_weights and 'survey_weight' in filt.columns) else None
    eff_n = effective_n(w) if w is not None else len(filt)

    mean_age_val      = weighted_mean(filt['r13agey_b'], w)
    mean_phenoage_val = weighted_mean(filt['phenoage'], w)
    mean_delta        = weighted_mean(filt['phenoage_delta'], w)
    pct_accel         = weighted_pct((filt['phenoage_delta'] > 0).astype(float), w)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Respondents", f"{len(filt):,}")
    c2.metric("Mean age", f"{mean_age_val:.1f}")
    c3.metric("Mean PhenoAge", f"{mean_phenoage_val:.1f}")
    c4.metric("Mean delta", f"{mean_delta:+.2f} yrs")
    c5.metric("% Accelerated", f"{pct_accel*100:.0f}%")

    if use_weights and w is not None:
        st.caption(f"Survey-weighted (R13WTRESP) - Effective n: {eff_n:,.0f}")
    else:
        st.caption("Unweighted sample averages.")

    delta_color = CORAL if mean_delta > 0 else TEAL
    st.markdown(
        f"""<div style='background:{NAVY};color:white;padding:24px 28px;
                    border-radius:10px;text-align:center;margin:16px 0;'>
            <div style='color:{GOLD};font-size:11px;letter-spacing:2px;
                        text-transform:uppercase;'>HRS 2016 - Venous Blood Study - n={len(filt):,}</div>
            <div style='font-size:48px;font-weight:800;margin-top:8px;'>
                <span style='color:{delta_color};'>{mean_delta:+.2f}</span>
                <span style='color:{GOLD};font-size:24px;'> years</span>
            </div>
            <div style='font-size:16px;color:#C9CBD4;margin-top:6px;'>
                mean biological age acceleration in Americans aged {age_range[0]}-{age_range[1]}
            </div>
        </div>""", unsafe_allow_html=True,
    )

    col1,col2 = st.columns(2)
    with col1:
        fig = px.histogram(filt, x='phenoage_delta', color='sex',
            color_discrete_map={'Male':NAVY,'Female':GOLD},
            nbins=50, title='PhenoAge Delta Distribution',
            labels={'phenoage_delta':'Biological Age Acceleration (years)'})
        fig.add_vline(x=0, line_dash='dash', line_color='gray')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig, width='stretch', key='vbs_delta_dist')
    with col2:
        ag = filt.groupby('age_group', observed=True)['phenoage_delta'].mean().reset_index()
        fig2 = px.bar(ag, x='age_group', y='phenoage_delta',
            title='Mean Biological Age Acceleration by Age Group',
            labels={'age_group':'Age Group','phenoage_delta':'Mean Delta (years)'},
            color_discrete_sequence=[CORAL])
        fig2.add_hline(y=0, line_dash='dash', line_color='gray')
        fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig2, width='stretch', key='vbs_age_group')

    filt2 = filt[filt['r13agey_b'].between(50,95)].copy()
    if not survey.empty:
        cog = survey[['respondent_id','cognitive_total']].rename(columns={'respondent_id':'hhidpn'})
        filt2 = filt2.merge(cog, on='hhidpn', how='left')
        if 'cognitive_total' in filt2.columns and filt2['cognitive_total'].notna().sum() > 100:
            filt2['pa_q'] = pd.qcut(filt2['phenoage_delta'], 5,
                labels=['Q1 (youngest)','Q2','Q3','Q4','Q5 (oldest)'])
            filt2['impaired'] = (filt2['cognitive_total'] < 18).astype(float)
            qi = filt2.groupby('pa_q', observed=True).agg(
                n=('cognitive_total','count'),
                mean_delta=('phenoage_delta','mean'),
                mean_cog=('cognitive_total','mean'),
                pct_impaired=('impaired','mean'),
            ).round(3)
            qi['pct_impaired'] = (qi['pct_impaired']*100).round(1)
            st.markdown("**Cognitive Impairment by PhenoAge Quintile**")
            st.dataframe(qi.rename(columns={
                'n':'n','mean_delta':'Mean Bio Age Accel (yrs)',
                'mean_cog':'Mean Cognitive Score','pct_impaired':'% Cognitively Impaired'
            }), width='stretch')

    st.caption("Source: HRS 2016 Venous Blood Study (restricted). PhenoAge: Levine et al. 2018.")


# TAB 2 - CLOCK COMPARISON
with tabs[1]:
    if not has_clocks:
        st.info("Epigenetic clock data not loaded. File: hrs_epigenetic_clocks.parquet")
    if not has_vbs:
        st.info("VBS PhenoAge data not loaded.")

    if has_clocks and has_vbs:
        merged = vbs[['hhidpn','r13agey_b','phenoage_delta','sex','race']].merge(
            clocks[['hhidpn','grimage2','grimage2_accel','dunedin_pace_methyl']],
            on='hhidpn', how='inner'
        )

        if has_poa:
            merged = merged.merge(
                poa[['hhidpn','dunedin_pace']].rename(columns={'dunedin_pace':'dunedin_pace_behav'}),
                on='hhidpn', how='left'
            )

        st.markdown(f"**Overlapping sample: {len(merged):,} respondents with both VBS PhenoAge and epigenetic clocks**")
        st.caption("All three clocks measured in the same individuals from the HRS 2016 Venous Blood Study.")

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("n (overlap)", f"{len(merged):,}")
        c2.metric("Mean PhenoAge delta", f"{merged['phenoage_delta'].mean():+.2f} yrs")
        c3.metric("Mean GrimAge2 accel.", f"{merged['grimage2_accel'].mean():+.2f} yrs")
        c4.metric("Mean DunedinPACE (methyl)", f"{merged['dunedin_pace_methyl'].mean():.3f}")

        col1, col2 = st.columns(2)
        with col1:
            fig = px.scatter(
                merged.sample(min(2000, len(merged)), random_state=42),
                x='phenoage_delta', y='grimage2_accel',
                color='sex', color_discrete_map={'Male':NAVY,'Female':GOLD},
                opacity=0.5,
                title='PhenoAge Delta vs GrimAge2 Acceleration',
                labels={'phenoage_delta':'PhenoAge Delta (yrs)',
                        'grimage2_accel':'GrimAge2 Acceleration (yrs)'},
            )
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
            st.plotly_chart(fig, width='stretch', key='clk_phenogrimage')

        with col2:
            fig2 = px.scatter(
                merged.dropna(subset=['dunedin_pace_methyl']).sample(
                    min(2000, merged['dunedin_pace_methyl'].notna().sum()), random_state=42),
                x='phenoage_delta', y='dunedin_pace_methyl',
                color='sex', color_discrete_map={'Male':NAVY,'Female':GOLD},
                opacity=0.5,
                title='PhenoAge Delta vs DunedinPACE (Methylation)',
                labels={'phenoage_delta':'PhenoAge Delta (yrs)',
                        'dunedin_pace_methyl':'DunedinPACE (yrs/yr)'},
            )
            fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
            st.plotly_chart(fig2, width='stretch', key='clk_phenodune')

        clock_cols = ['phenoage_delta','grimage2_accel','dunedin_pace_methyl']
        if 'dunedin_pace_behav' in merged.columns:
            clock_cols.append('dunedin_pace_behav')
        corr_df = merged[clock_cols].corr().round(3)
        st.markdown("**Correlation Matrix - Biological Age Clocks**")
        st.dataframe(corr_df, width='stretch')
        st.caption(
            "PhenoAge = clinical biomarker approach (9 standard blood tests, ~$30-50). "
            "GrimAge2 / DunedinPACE (methyl) = DNA methylation approach (~$300-500/patient). "
            "Correlation shows how aligned the clinical and epigenetic approaches are in the same individuals."
        )

    if has_poa and not has_clocks:
        st.markdown("**DunedinPACE Distribution (HRS Pace of Aging)**")
        fig = px.histogram(poa, x='dunedin_pace', nbins=60,
            title='DunedinPACE Distribution (n=13,358)',
            labels={'dunedin_pace':'DunedinPACE (years per calendar year)'},
            color_discrete_sequence=[NAVY])
        fig.add_vline(x=1.0, line_dash='dash', line_color=GOLD,
                      annotation_text='Average pace (1.0)', annotation_position='top right')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig, width='stretch', key='clk_poa_hist')
        st.caption("Values >1.0 = aging faster than average. Mean: 1.49. Source: Balachandran et al. 2025, Nature Aging.")


# TAB 3 - LONGITUDINAL BIOMARKERS (DBS)
with tabs[2]:
    if not has_dbs:
        st.info("DBS longitudinal data not loaded. File: hrs_dbs_longitudinal.parquet")
    else:
        st.markdown(f"**{len(dbs):,} observations - {dbs['hhidpn'].nunique():,} unique respondents - 6 waves (2006-2016)**")

        biomarker_labels = {
            'hba1c':      'HbA1c (%)',
            'crp':        'CRP (mg/L)',
            'total_chol': 'Total Cholesterol (mg/dL)',
            'hdl':        'HDL Cholesterol (mg/dL)',
            'cystatin_c': 'Cystatin-C (mg/L)',
        }

        st.markdown("#### Population-Level Biomarker Trends (2006-2016)")
        trend = dbs.groupby('wave_year')[list(biomarker_labels.keys())].mean().reset_index()

        col1, col2 = st.columns(2)
        with col1:
            fig = go.Figure()
            for bm, label in [('hba1c','HbA1c (%)'),('crp','CRP (mg/L)')]:
                fig.add_trace(go.Scatter(
                    x=trend['wave_year'], y=trend[bm], mode='lines+markers',
                    name=label, line=dict(width=2),
                ))
            fig.update_layout(
                title='Metabolic Markers Over Time',
                xaxis_title='Wave Year', yaxis_title='Mean Value',
                plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
                legend=dict(orientation='h', y=-0.2),
            )
            st.plotly_chart(fig, width='stretch', key='dbs_metabolic')

        with col2:
            fig2 = go.Figure()
            for bm, label in [('total_chol','Total Cholesterol'),('hdl','HDL')]:
                fig2.add_trace(go.Scatter(
                    x=trend['wave_year'], y=trend[bm], mode='lines+markers',
                    name=label, line=dict(width=2),
                ))
            fig2.update_layout(
                title='Lipid Markers Over Time',
                xaxis_title='Wave Year', yaxis_title='Mean Value (mg/dL)',
                plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
                legend=dict(orientation='h', y=-0.2),
            )
            st.plotly_chart(fig2, width='stretch', key='dbs_lipids')

        st.markdown("#### Individual Biomarker Trajectories")
        st.caption("Select a biomarker to see the distribution of individual trajectories across waves.")

        bm_choice = st.selectbox("Biomarker", list(biomarker_labels.keys()),
                                 format_func=lambda x: biomarker_labels[x], key="dbs_bm")

        valid_dbs = dbs[dbs[bm_choice].notna()].copy()
        fig3 = px.box(
            valid_dbs, x='wave_year', y=bm_choice,
            title=f'{biomarker_labels[bm_choice]} Distribution by Wave',
            labels={'wave_year':'Wave Year', bm_choice: biomarker_labels[bm_choice]},
            color_discrete_sequence=[NAVY],
        )
        fig3.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
        st.plotly_chart(fig3, width='stretch', key='dbs_boxplot')

        wave_summary = dbs.groupby('wave_year')[list(biomarker_labels.keys())].agg(['mean','std']).round(3)
        wave_summary.columns = [f'{b} ({s})' for b, s in wave_summary.columns]
        st.markdown("**Wave-Level Summary Statistics**")
        st.dataframe(wave_summary, width='stretch')

        st.caption(
            "Source: HRS Dried Blood Spot (DBS) biomarker panels, waves 2006-2016. "
            "Restricted access - University of Michigan / NIA."
        )


# TAB 4 - HEALTH & FUNCTION
with tabs[3]:
    if survey.empty:
        st.warning("Survey data not found.")
    else:
        sf = survey[survey['age'].between(50, 95)].copy()
        sf_w = sf['survey_weight'].to_numpy() if ('survey_weight' in sf.columns and st.session_state.get('vbs_weighted', True)) else None
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Respondents", f"{len(sf):,}")
        c2.metric("Mean age", f"{weighted_mean(sf['age'], sf_w):.1f}")
        c3.metric("Mean cognitive score", f"{weighted_mean(sf['cognitive_total'], sf_w):.1f} / 35")
        c4.metric("Mean conditions", f"{weighted_mean(sf['condition_count'], sf_w):.1f}")
        if sf_w is not None:
            st.caption(f"Survey-weighted (R13WTRESP) - Effective n: {effective_n(sf_w):,.0f}")

        conditions = {"Hypertension":"hypertension","Diabetes":"diabetes",
                      "Heart Disease":"heart_disease","Stroke":"stroke",
                      "Arthritis":"arthritis","Lung Disease":"lung_disease"}

        col1,col2 = st.columns(2)
        with col1:
            prev = [{"Condition":k,
                     "Prevalence (%)": weighted_pct(sf[v].astype(float), sf_w)*100}
                    for k,v in conditions.items()]
            fig = px.bar(pd.DataFrame(prev).sort_values("Prevalence (%)"),
                         x="Prevalence (%)",y="Condition",orientation="h",
                         title="Chronic Condition Prevalence",
                         color_discrete_sequence=[CORAL])
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                              font_color='#1A1A2E', xaxis=dict(range=[0,100],ticksuffix="%"))
            st.plotly_chart(fig, width='stretch', key='health_conditions')
        with col2:
            cog_age = sf.groupby('age_group', observed=True)['cognitive_total'].mean().reset_index()
            fig2 = px.bar(cog_age, x='age_group', y='cognitive_total',
                          title='Mean Cognitive Score by Age Group',
                          color_discrete_sequence=[TEAL],
                          labels={'age_group':'Age Group','cognitive_total':'Mean Score (0-35)'})
            fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
            st.plotly_chart(fig2, width='stretch', key='health_cog')


# TAB 5 - DEMOGRAPHICS
with tabs[4]:
    if survey.empty:
        st.warning("Survey data not found.")
    else:
        col1,col2 = st.columns(2)
        with col1:
            fig = px.histogram(survey, x='age', color='sex',
                color_discrete_map={'Male':NAVY,'Female':GOLD},
                nbins=30, title='Age Distribution by Sex',
                labels={'age':'Age (years)'})
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
            st.plotly_chart(fig, width='stretch', key='demo_age')
        with col2:
            srh_order = ["Excellent","Very Good","Good","Fair","Poor"]
            srh = survey['self_rated_health_label'].value_counts().reindex(srh_order).reset_index()
            srh.columns = ['Rating','Count']
            fig2 = px.bar(srh, x='Rating', y='Count', title='Self-Rated Health',
                          color_discrete_sequence=[NAVY])
            fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E')
            st.plotly_chart(fig2, width='stretch', key='demo_srh')
