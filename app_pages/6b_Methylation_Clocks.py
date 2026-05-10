"""
Methylation Clocks - registry v0.

Built on the methylation-clock outputs we already have in HRS:
  - GrimAge2 + GrimAge2 acceleration (n=4,018)
  - DunedinPACE methylation (n=4,018)
  - DunedinPACE behavioral (n=13,358)
  - DNAm-imputed log(CRP) and log(HbA1c) bonus columns

This page exposes those clocks at the population level and frames the
registry architecture so UK Biobank CpG-level data drops in cleanly when
that application clears. Today's data is HRS-only; the structure here is
designed to extend to any cohort with methylation arrays.

Tabs:
  1. Methylation overview
  2. GrimAge2
  3. DunedinPACE (methylation)
  4. DunedinPACE (behavioral)
  5. Cross-clock concordance + roadmap
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.config import (data_exists, NAVY, GOLD, CORAL, TEAL,
                        HRS_VBS_PARQUET, HRS_EPIGEN_PARQUET, HRS_POA_PARQUET)

st.set_page_config(page_title="Methylation Clocks - INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Methylation Clocks <span style='font-size:16px;color:{GOLD};
            font-weight:500;letter-spacing:0;'>- registry v0</span></div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            HRS GrimAge2 + DunedinPACE (methyl) + DunedinPACE (behavioral).
            Architecture extends to UK Biobank CpG-level data on application clearance.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Loaders ----------
@st.cache_data
def load_vbs():
    if not data_exists(HRS_VBS_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(HRS_VBS_PARQUET)
    df['hhidpn'] = pd.to_numeric(df['hhidpn'], errors='coerce')
    df['sex_label']  = df['ragender'].map({1: 'Male', 2: 'Female'})
    df['race_label'] = df['raracem'].map({1: 'White', 2: 'Black', 3: 'Other'})
    return df

@st.cache_data
def load_ec():
    if not data_exists(HRS_EPIGEN_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(HRS_EPIGEN_PARQUET)
    df['hhidpn'] = pd.to_numeric(df['hhidpn'], errors='coerce')
    return df

@st.cache_data
def load_poa():
    if not data_exists(HRS_POA_PARQUET):
        return pd.DataFrame()
    df = pd.read_parquet(HRS_POA_PARQUET)
    df['hhidpn'] = pd.to_numeric(df['hhidpn'], errors='coerce')
    return df

vbs = load_vbs()
ec  = load_ec()
poa = load_poa()
have = (not vbs.empty) and (not ec.empty)
have_poa = not poa.empty

if not have:
    st.warning("Methylation clock data not found. Need hrs_vbs_with_phenoage.parquet "
               "and hrs_epigenetic_clocks.parquet in S3.")
    st.stop()

# Master merged frame: VBS + GrimAge2 + DunedinPACE (methyl) + DunedinPACE (behav)
merged = vbs.merge(ec, on='hhidpn', how='inner')
if have_poa:
    merged = merged.merge(
        poa[['hhidpn','dunedin_pace']].rename(columns={'dunedin_pace':'dunedin_pace_behav'}),
        on='hhidpn', how='left',
    )

# Larger DunedinPACE (behav) sample joined just for the standalone tab
poa_with_vbs = vbs[['hhidpn','r13agey_b','ragender','raracem','sex_label','race_label',
                     'mortality_status','years_to_event','phenoage','phenoage_delta']].merge(
    poa[['hhidpn','dunedin_pace','age_poa_baseline','sex_label']]
        .rename(columns={'sex_label':'sex_label_poa'}),
    on='hhidpn', how='inner',
) if have_poa else pd.DataFrame()


# ---------- Cox helper ----------
@st.cache_data
def age_adj_cox(df_dict, x_col, time_col, event_col, age_col):
    try:
        from lifelines import CoxPHFitter
    except ImportError:
        return None
    sub = pd.DataFrame(df_dict).dropna()
    sub = sub[sub[time_col] > 0]
    if len(sub) < 100 or sub[event_col].sum() < 30:
        return None
    cph = CoxPHFitter()
    try:
        cph.fit(sub, duration_col=time_col, event_col=event_col)
    except Exception:
        return None
    s = cph.summary.loc[x_col]
    return {
        "n": int(len(sub)), "events": int(sub[event_col].sum()),
        "hr": float(s["exp(coef)"]),
        "lo": float(s["exp(coef) lower 95%"]),
        "hi": float(s["exp(coef) upper 95%"]),
        "p":  float(s["p"]),
        "c":  float(cph.concordance_index_),
    }


def _km_quintile(df, x_col, time_col, event_col, title):
    try:
        from lifelines import KaplanMeierFitter
    except ImportError:
        return None
    sub = df[[x_col, time_col, event_col]].dropna()
    sub = sub[sub[time_col] > 0]
    if len(sub) < 200:
        return None
    sub['q'] = pd.qcut(sub[x_col], 5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
    palette = [TEAL, "#7FB069", GOLD, "#E8A85B", CORAL]
    fig = go.Figure()
    for q, color in zip(['Q1','Q2','Q3','Q4','Q5'], palette):
        s = sub[sub['q'] == q]
        if len(s) < 30:
            continue
        kmf = KaplanMeierFitter()
        kmf.fit(s[time_col], s[event_col], label=str(q))
        sf = kmf.survival_function_
        fig.add_trace(go.Scatter(x=sf.index, y=sf.iloc[:, 0], mode='lines',
                                  name=str(q), line=dict(color=color, width=2.5)))
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=380,
                      xaxis_title='Years from baseline',
                      yaxis_title='Survival probability',
                      yaxis=dict(range=[0.4, 1.01]),
                      title=title)
    return fig


def _hero(label, cox_dict, sample_note=""):
    if cox_dict is None:
        st.warning(f"Cox validation unavailable for {label} (need lifelines + mortality follow-up).")
        return
    hr, lo, hi, c = cox_dict["hr"], cox_dict["lo"], cox_dict["hi"], cox_dict["c"]
    color = CORAL if hr > 1.0 else TEAL
    st.markdown(
        f"""<div style='background:{NAVY};color:white;padding:22px 28px;
                    border-radius:10px;margin:8px 0 16px 0;'>
            <div style='color:{GOLD};font-size:11px;letter-spacing:2px;
                        text-transform:uppercase;'>{label} - age-adjusted Cox PH</div>
            <div style='display:flex;gap:42px;margin-top:10px;align-items:flex-end;'>
                <div>
                    <div style='font-size:42px;font-weight:800;color:{color};line-height:1;'>
                        {hr:.3f}
                    </div>
                    <div style='font-size:12px;color:#C9CBD4;margin-top:4px;'>
                        HR per 1-unit advance &nbsp; [{lo:.3f}, {hi:.3f}]
                    </div>
                </div>
                <div>
                    <div style='font-size:32px;font-weight:700;color:{GOLD};line-height:1;'>
                        {c:.3f}
                    </div>
                    <div style='font-size:12px;color:#C9CBD4;margin-top:4px;'>C-index</div>
                </div>
                <div>
                    <div style='font-size:24px;font-weight:600;color:white;line-height:1;'>
                        {cox_dict['n']:,} / {cox_dict['events']:,}
                    </div>
                    <div style='font-size:12px;color:#C9CBD4;margin-top:4px;'>n / events</div>
                </div>
                <div style='font-size:12px;color:#C9CBD4;align-self:center;flex-grow:1;'>
                    {sample_note}
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def _by_age_decade(df, x_col, label, color):
    sub = df[['r13agey_b', x_col]].dropna().copy()
    sub['age_decade'] = (sub['r13agey_b'] // 10 * 10).astype(int).clip(50, 90)
    ag = sub.groupby('age_decade')[x_col].agg(['mean', 'std', 'count']).reset_index()
    fig = px.bar(ag, x='age_decade', y='mean', error_y='std',
                  title=f'Mean {label} by age decade',
                  color_discrete_sequence=[color],
                  labels={'age_decade': 'Age decade',
                          'mean': f'Mean {label}'})
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=320,
                      margin=dict(t=40, b=40, l=40, r=20))
    return fig


def _vs_phenoage(df, x_col, label, color):
    sub = df[[x_col, 'phenoage_delta', 'sex_label']].dropna()
    if len(sub) < 100:
        return None
    sub = sub.sample(min(2500, len(sub)), random_state=42)
    r = sub[[x_col, 'phenoage_delta']].corr().iloc[0, 1]
    fig = px.scatter(sub, x='phenoage_delta', y=x_col, color='sex_label',
                      color_discrete_map={'Male': NAVY, 'Female': GOLD},
                      opacity=0.5,
                      title=f'{label} vs biomarker PhenoAge delta (r={r:+.3f})',
                      labels={'phenoage_delta': 'PhenoAge delta (yrs)',
                              x_col: label})
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                      font_color='#1A1A2E', height=360,
                      legend_title_text='Sex')
    return fig


# ---------- Tabs ----------
tabs = st.tabs([
    "Overview",
    "GrimAge2",
    "DunedinPACE (methyl)",
    "DunedinPACE (behavioral)",
    "Concordance + roadmap",
])

# Tab 1 - Overview
with tabs[0]:
    st.markdown("#### What's in the methylation registry today")
    st.caption(
        "INEXION's methylation layer currently uses HRS clock outputs - GrimAge2, "
        "DunedinPACE, and DNAm-imputed CRP/HbA1c. Underlying CpG-level methylation "
        "data is not yet ingested; that's gated on the UK Biobank application. "
        "When UKB clears, this same page will surface UKB methylation in addition "
        "to HRS, with consistent Cox / KM / concordance plumbing."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("HRS w/ GrimAge2", f"{len(ec):,}")
    c2.metric("HRS w/ DunedinPACE methyl", f"{ec['dunedin_pace_methyl'].notna().sum():,}")
    c3.metric("HRS w/ DunedinPACE behav", f"{len(poa):,}" if have_poa else "0")
    overlap = vbs[['hhidpn']].merge(ec[['hhidpn']], on='hhidpn').shape[0]
    c4.metric("Overlap w/ VBS PhenoAge", f"{overlap:,}")

    st.markdown("##### Sample distribution")
    cA, cB = st.columns(2)
    with cA:
        ag = vbs[['hhidpn','r13agey_b','sex_label']].merge(
            ec[['hhidpn']], on='hhidpn', how='inner').dropna()
        fig = px.histogram(ag, x='r13agey_b', color='sex_label',
                            color_discrete_map={'Male':NAVY,'Female':GOLD},
                            nbins=30, title='Age distribution of methylation sample',
                            labels={'r13agey_b':'Age (years)'})
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                          font_color='#1A1A2E', height=320)
        st.plotly_chart(fig, width='stretch', key='meth_age_dist')
    with cB:
        rg = vbs[['hhidpn','race_label']].merge(
            ec[['hhidpn']], on='hhidpn', how='inner').dropna()
        rc = rg['race_label'].value_counts().reset_index()
        rc.columns = ['Race', 'Count']
        fig = px.bar(rc, x='Race', y='Count',
                      title='Race composition of methylation sample',
                      color_discrete_sequence=[CORAL])
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                          font_color='#1A1A2E', height=320)
        st.plotly_chart(fig, width='stretch', key='meth_race')

    st.caption(
        "GrimAge2 + DunedinPACE methyl available in the same 4,018 individuals - "
        "a complete head-to-head sample. DunedinPACE behavioral is a larger but "
        "non-overlapping cohort with weaker direct mortality power per unit advance "
        "but a much bigger n."
    )


# Tab 2 - GrimAge2
with tabs[1]:
    st.caption(
        "GrimAge2 (Lu et al., 2022) is the second-generation epigenetic clock trained "
        "on time-to-mortality. Acceleration = residual after regressing GrimAge2 on "
        "chronological age. Among 4,018 HRS Wave 13 respondents."
    )
    cox_g = age_adj_cox(
        merged[['grimage2_accel', 'years_to_event', 'mortality_status', 'r13agey_b']].to_dict('list'),
        'grimage2_accel', 'years_to_event', 'mortality_status', 'r13agey_b',
    )
    _hero("HRS GrimAge2 acceleration", cox_g, "Adjusted for chronological age (r13agey_b).")

    cA, cB = st.columns(2)
    with cA:
        fig = px.histogram(merged, x='grimage2_accel', nbins=50, color='sex_label',
                            color_discrete_map={'Male':NAVY,'Female':GOLD},
                            title='GrimAge2 acceleration distribution')
        fig.add_vline(x=0, line_dash='dash', line_color='gray')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                          font_color='#1A1A2E', height=320)
        st.plotly_chart(fig, width='stretch', key='meth_g_dist')
    with cB:
        st.plotly_chart(_by_age_decade(merged, 'grimage2_accel', 'GrimAge2 accel.',
                                         CORAL), width='stretch', key='meth_g_dec')

    km = _km_quintile(merged, 'grimage2_accel', 'years_to_event', 'mortality_status',
                      'KM survival by quintile of GrimAge2 acceleration')
    if km:
        st.plotly_chart(km, width='stretch', key='meth_g_km')

    fig_vs = _vs_phenoage(merged, 'grimage2_accel', 'GrimAge2 acceleration', NAVY)
    if fig_vs:
        st.plotly_chart(fig_vs, width='stretch', key='meth_g_vs_pa')


# Tab 3 - DunedinPACE methylation
with tabs[2]:
    st.caption(
        "DunedinPACE (Belsky et al., 2022) measures the rate of biological aging. "
        "Values > 1.0 = aging faster than 1 year per chronological year. The "
        "methylation version is direct from CpG sites; the behavioral version "
        "(next tab) imputes pace from DNAm-derived behavioral surrogates."
    )
    cox_d = age_adj_cox(
        merged[['dunedin_pace_methyl', 'years_to_event', 'mortality_status', 'r13agey_b']].to_dict('list'),
        'dunedin_pace_methyl', 'years_to_event', 'mortality_status', 'r13agey_b',
    )
    _hero("HRS DunedinPACE (methylation)", cox_d, "Note: HR is per 1-unit pace - very large because pace SD is small.")

    cA, cB = st.columns(2)
    with cA:
        fig = px.histogram(merged, x='dunedin_pace_methyl', nbins=50, color='sex_label',
                            color_discrete_map={'Male':NAVY,'Female':GOLD},
                            title='DunedinPACE (methyl) distribution')
        fig.add_vline(x=1.0, line_dash='dash', line_color=GOLD,
                      annotation_text='Pace = 1.0', annotation_position='top right')
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                          font_color='#1A1A2E', height=320)
        st.plotly_chart(fig, width='stretch', key='meth_d_dist')
    with cB:
        st.plotly_chart(_by_age_decade(merged, 'dunedin_pace_methyl',
                                         'DunedinPACE (methyl)', "#A66B36"),
                         width='stretch', key='meth_d_dec')

    km = _km_quintile(merged, 'dunedin_pace_methyl', 'years_to_event', 'mortality_status',
                      'KM survival by quintile of DunedinPACE (methylation)')
    if km:
        st.plotly_chart(km, width='stretch', key='meth_d_km')

    fig_vs = _vs_phenoage(merged, 'dunedin_pace_methyl', 'DunedinPACE (methyl)', NAVY)
    if fig_vs:
        st.plotly_chart(fig_vs, width='stretch', key='meth_d_vs_pa')


# Tab 4 - DunedinPACE behavioral
with tabs[3]:
    if not have_poa or poa_with_vbs.empty:
        st.info("DunedinPACE behavioral data not loaded.")
    else:
        st.caption(
            "DunedinPACE behavioral - the wider HRS sample (n=13,358) where "
            "DunedinPACE was estimated from DNAm-derived behavioral surrogates "
            "rather than direct methylation. Larger n, slightly lower per-unit "
            "discrimination than the methylation version, but higher total power."
        )
        cox_b = age_adj_cox(
            poa_with_vbs[['dunedin_pace', 'years_to_event', 'mortality_status', 'r13agey_b']].to_dict('list'),
            'dunedin_pace', 'years_to_event', 'mortality_status', 'r13agey_b',
        )
        _hero("HRS DunedinPACE (behavioral)", cox_b,
              f"Larger sample - n=13,358 in DunedinPACE file; {len(poa_with_vbs):,} merge into VBS for mortality.")

        cA, cB = st.columns(2)
        with cA:
            fig = px.histogram(poa_with_vbs, x='dunedin_pace', nbins=60,
                                title='DunedinPACE (behavioral) distribution',
                                color_discrete_sequence=[NAVY])
            fig.add_vline(x=1.0, line_dash='dash', line_color=GOLD,
                          annotation_text='Pace = 1.0',
                          annotation_position='top right')
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                              font_color='#1A1A2E', height=320)
            st.plotly_chart(fig, width='stretch', key='meth_b_dist')
        with cB:
            st.plotly_chart(_by_age_decade(poa_with_vbs, 'dunedin_pace',
                                             'DunedinPACE (behav)', GOLD),
                             width='stretch', key='meth_b_dec')

        km = _km_quintile(poa_with_vbs, 'dunedin_pace', 'years_to_event', 'mortality_status',
                          'KM survival by quintile of DunedinPACE (behavioral)')
        if km:
            st.plotly_chart(km, width='stretch', key='meth_b_km')


# Tab 5 - Concordance + roadmap
with tabs[4]:
    st.markdown("#### Inter-clock correlation")
    st.caption(
        "Same 4,018-respondent sample. How aligned are the four clocks at a "
        "continuous level?"
    )
    cols = ['phenoage_delta', 'grimage2_accel', 'dunedin_pace_methyl']
    if 'dunedin_pace_behav' in merged.columns:
        cols.append('dunedin_pace_behav')
    labels = {'phenoage_delta':'Biomarker PhenoAge delta',
              'grimage2_accel':'GrimAge2 acceleration',
              'dunedin_pace_methyl':'DunedinPACE (methyl)',
              'dunedin_pace_behav':'DunedinPACE (behav)'}
    sub = merged[cols].dropna()
    if len(sub) > 100:
        corr = sub.corr().rename(index=labels, columns=labels).round(3)
        fig = px.imshow(corr, text_auto=True, aspect='equal',
                         color_continuous_scale='RdBu_r', zmin=-1, zmax=1)
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white',
                          font_color='#1A1A2E', height=360,
                          margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, width='stretch', key='meth_corr')
        st.caption(f"Pairwise n = {len(sub):,}.")

    st.markdown("---")
    st.markdown("#### Top-quintile concordance")
    st.caption(
        "Across clocks, who flags as the 'fastest 20%'? Jaccard similarity of "
        "top-quintile membership tells you whether you'd intervene on different "
        "patients depending on which clock you ran."
    )
    rdf = merged[['phenoage_delta','grimage2_accel','dunedin_pace_methyl']].dropna()
    if len(rdf) > 100:
        top = {c: set(rdf[rdf[c] >= rdf[c].quantile(0.8)].index)
               for c in rdf.columns}
        rows = []
        col_list = list(rdf.columns)
        for i, c1 in enumerate(col_list):
            for c2 in col_list[i+1:]:
                j = len(top[c1] & top[c2]) / len(top[c1] | top[c2])
                rows.append({'Clock A': labels[c1], 'Clock B': labels[c2],
                              'Jaccard (top quintile)': round(j, 3)})
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        st.caption(
            "All three pairwise Jaccards are well below 0.5. Identifying who "
            "is 'aging fastest' depends substantially on which clock is used - "
            "a strong argument for INEXION shipping multi-clock readouts rather "
            "than betting on any single methodology."
        )

    st.markdown("---")
    st.markdown("#### Roadmap to UK Biobank methylation")
    st.markdown(
        "**v0 (today)** - HRS clock outputs only. GrimAge2, DunedinPACE methyl, "
        "DunedinPACE behavioral, DNAm-imputed CRP / HbA1c. ~4,018 to ~13,358 n."
        "  \n  "
        "**v1 (UKB pending)** - UKB methylation array (n ~ 50K with M-arrays). "
        "Refit GrimAge2 / DunedinPACE within UKB. Ingest CpG-level betas to "
        "S3 `s3://inexion-registry/raw/methylation/ukb/`. Add per-CpG covariates "
        "to the registry schema."
        "  \n  "
        "**v2 (future)** - SYMPHONYAge organ-specific methylation clocks "
        "(Raghav's primary research). Plug into the existing `pages/6_Organ_Ages.py` "
        "framework so each organ gets a methylation companion to its biomarker clock."
        "  \n  "
        "**v3 (future)** - INEXION-cohort methylation. Once partner clinics "
        "(Healthspan and successors) start running methylation panels on patients, "
        "those data flow into the registry under DUA + de-identification."
    )
    st.caption(
        "Page architecture is methodology-agnostic - a clock contributes a column, "
        "the page renders it. Adding UK Biobank means a new dataset loader and new "
        "tabs, no refactor of the per-clock plumbing."
    )
