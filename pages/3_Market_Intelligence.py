"""
Market Intelligence — BRFSS 2024 Longevity Market Targeting
Where are INEXION's best clinic acquisition and patient acquisition markets?
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.config import NAVY, GOLD, CORAL, TEAL, BRFSS_STATE_PARQUET, BRFSS_METRO_PARQUET, data_exists

st.set_page_config(page_title="Market Intelligence — INEXION Registry", layout="wide")

st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Market Intelligence</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            BRFSS 2024 · n=457,670 · Longevity Market Score by state and metro type
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

@st.cache_data
def load_data():
    state = pd.read_parquet(BRFSS_STATE_PARQUET) if data_exists(BRFSS_STATE_PARQUET) else pd.DataFrame()
    metro = pd.read_parquet(BRFSS_METRO_PARQUET) if data_exists(BRFSS_METRO_PARQUET) else pd.DataFrame()
    return state, metro

state_df, metro_df = load_data()

if state_df.empty:
    st.error("BRFSS data not found. Run `build_brfss_parquet.py` and upload to S3.")
    st.stop()

# ── Methodology callout ───────────────────────────────────────────────────────
with st.expander("How the Longevity Market Score is computed"):
    st.markdown(
        "**Composite Longevity Market Score** (0–100, normalized within dataset)\n\n"
        "| Component | Weight | Measure |\n"
        "|---|---|---|\n"
        "| Income ≥$50K | 40% | % of respondents in household income bracket $50K+ |\n"
        "| Any exercise | 20% | % reporting any physical activity in past 30 days |\n"
        "| Good/Very Good health | 15% | % self-rating health as Good or Very Good |\n"
        "| Has personal doctor | 15% | % reporting at least one personal physician |\n"
        "| Recent checkup | 10% | % with checkup within past year |\n\n"
        "Source: CDC BRFSS 2024 public-use data. Survey-weighted estimates using `_LLCPWT`."
    )

# ── State rankings ────────────────────────────────────────────────────────────
st.markdown("### State Rankings — Longevity Market Score")

col1, col2 = st.columns([3, 2])

with col1:
    n_states = st.slider("Show top N states", 10, 51, 20, key="n_states")
    top_states = state_df.head(n_states).copy()

    fig = go.Figure(go.Bar(
        x=top_states['market_score'],
        y=top_states['state_name'],
        orientation='h',
        marker=dict(
            color=top_states['market_score'],
            colorscale=[[0, '#2E74B5'], [0.5, GOLD], [1, CORAL]],
            showscale=False,
        ),
        text=[f"{s:.0f}" for s in top_states['market_score']],
        textposition='outside',
    ))
    fig.update_layout(
        title=f'Top {n_states} States by Longevity Market Score',
        xaxis_title='Market Score (0–100)',
        yaxis=dict(autorange='reversed'),
        plot_bgcolor='white', paper_bgcolor='white',
        font_color='#1A1A2E', height=max(400, n_states * 22),
        margin=dict(l=150, r=80),
    )
    st.plotly_chart(fig, width='stretch', key='state_bar')

with col2:
    st.markdown("**Top 15 States — Detail**")
    display_cols = {
        'rank': 'Rank', 'state_name': 'State', 'market_score': 'Score',
        'pct_income_50k': '% Income $50K+', 'pct_exercises': '% Exercises',
        'pct_good_health': '% Good Health', 'pct_has_pcp': '% Has PCP',
    }
    st.dataframe(
        state_df.head(15)[list(display_cols.keys())].rename(columns=display_cols)
        .round(1).reset_index(drop=True),
        width='stretch', key='state_table'
    )

# ── US Choropleth ─────────────────────────────────────────────────────────────
st.markdown("### Geographic Distribution")

# Add state abbreviations for choropleth
STATE_ABBR = {
    'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA',
    'Colorado':'CO','Connecticut':'CT','Delaware':'DE','DC':'DC','Florida':'FL',
    'Georgia':'GA','Hawaii':'HI','Idaho':'ID','Illinois':'IL','Indiana':'IN',
    'Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME',
    'Maryland':'MD','Massachusetts':'MA','Michigan':'MI','Minnesota':'MN',
    'Mississippi':'MS','Missouri':'MO','Montana':'MT','Nebraska':'NE',
    'Nevada':'NV','New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM',
    'New York':'NY','North Carolina':'NC','North Dakota':'ND','Ohio':'OH',
    'Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA','Rhode Island':'RI',
    'South Carolina':'SC','South Dakota':'SD','Tennessee':'TN','Texas':'TX',
    'Utah':'UT','Vermont':'VT','Virginia':'VA','Washington':'WA',
    'West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY',
}
map_df = state_df.copy()
map_df['abbr'] = map_df['state_name'].map(STATE_ABBR)
map_df = map_df.dropna(subset=['abbr'])

fig_map = px.choropleth(
    map_df, locations='abbr', locationmode='USA-states',
    color='market_score', scope='usa',
    color_continuous_scale=['#E8EDF5', '#2E74B5', NAVY],
    range_color=[map_df['market_score'].min(), map_df['market_score'].max()],
    hover_name='state_name',
    hover_data={'market_score': ':.0f', 'pct_income_50k': ':.1f',
                'pct_exercises': ':.1f', 'abbr': False},
    labels={'market_score': 'Market Score'},
    title='INEXION Longevity Market Score by State',
)
fig_map.update_layout(
    geo=dict(showlakes=False, lakecolor='white'),
    paper_bgcolor='white', font_color='#1A1A2E', height=450,
    margin=dict(t=50, b=0, l=0, r=0),
)
st.plotly_chart(fig_map, width='stretch', key='choropleth')

# ── Metro breakdown ───────────────────────────────────────────────────────────
st.markdown("### Metro-Type Breakdown")
st.caption("Suburban MSA = suburbs of major metro areas. City MSA = urban core. Non-metro = rural and small town.")

metro_clean = metro_df[metro_df['metro_label'].isin(['City MSA','Suburban MSA','Non-metro'])].copy()
metro_pivot = metro_clean.pivot_table(
    index='state_name', columns='metro_label',
    values='market_score', aggfunc='first'
).reset_index().fillna(0)

# Top 15 by best metro score
metro_pivot['best'] = metro_pivot[['City MSA','Suburban MSA','Non-metro']].max(axis=1)
metro_pivot = metro_pivot.sort_values('best', ascending=False).head(15)

fig_metro = go.Figure()
for col, color in [('Suburban MSA', GOLD), ('City MSA', NAVY), ('Non-metro', TEAL)]:
    if col in metro_pivot.columns:
        fig_metro.add_trace(go.Bar(
            name=col, x=metro_pivot['state_name'],
            y=metro_pivot[col], marker_color=color,
        ))
fig_metro.update_layout(
    barmode='group', title='Market Score by State and Metro Type (Top 15 States)',
    xaxis_title='State', yaxis_title='Market Score',
    plot_bgcolor='white', paper_bgcolor='white', font_color='#1A1A2E',
    legend=dict(orientation='h', y=1.02), height=420,
)
st.plotly_chart(fig_metro, width='stretch', key='metro_bar')

# Key insight callout
st.markdown(
    f"""<div style='background:#F2F4F8;border-left:4px solid {GOLD};
    padding:16px 20px;border-radius:4px;margin-top:16px;'>
    <strong>INEXION Market Intelligence Finding</strong> — Suburban MSAs consistently
    outperform urban cores in longevity market score. The DC corridor (Maryland and Virginia
    suburban MSAs), Mountain West (Utah, Colorado), and New England (NH, VT, CT) represent
    the highest-density longevity patient markets in the U.S. California and Texas, despite
    large populations, underperform due to income inequality and lower exercise rates respectively.
    </div>""",
    unsafe_allow_html=True,
)

st.markdown("---")
st.caption(
    "Source: CDC BRFSS 2024 public-use data (n=457,670). "
    "Survey-weighted estimates using LLCPWT. "
    "Longevity Market Score = 40% income + 20% exercise + 15% health + 15% PCP + 10% checkup."
)
