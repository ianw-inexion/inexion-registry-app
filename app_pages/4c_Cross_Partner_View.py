"""
Cross-Partner View
==================

The marquee surface for the registry. AgelessRx H6 produces independent
matched-NHANES estimates for two completely different partners and asks
whether they replicate.

This page makes the answer legible in one screen: side-by-side forest plot,
95% CI overlap visualization, verdict callout (STRONG / DIRECTIONAL / FAIL),
and class-aligned subgroup comparisons where both partners overlap on
intervention class.

This is the highest-strategic finding the Inexion Longevity Registry can
produce - independent replication is what HEOR and pharma analytics buyers
care about above all else.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import NAVY, GOLD, CORAL, TEAL, BRAND_COLORWAY
from analytics.lib.run_loader import latest_run, format_ran_at

st.set_page_config(page_title="Cross-Partner View - INEXION Registry", layout="wide")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Longevity Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Cross-Partner Replication</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Independent matched-NHANES estimates from two longevity partners.
            Replication is the credential pharma analytics teams ask for first.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


rec = latest_run("AGELESSRX_H6")

if rec is None:
    st.error(
        "No AGELESSRX_H6 run found in analytics/runs/. "
        "Run analytics/hypotheses/agelessrx_h6_cross_partner_replication.py to populate this view."
    )
    st.stop()


# ---------------------------------------------------------------------------
# Provenance strip
# ---------------------------------------------------------------------------
cols = st.columns([1.4, 1.5, 1, 1.5, 1])
cols[0].markdown(f"**Run ID**\n\n`{rec.run_id}`")
cols[1].markdown(f"**Ran at**\n\n{format_ran_at(rec.ran_at)}")
cols[2].markdown(f"**Commit**\n\n`{rec.manifest.get('code_commit_hash', '?')[:12]}`")
cols[3].markdown(f"**Reference**\n\n{rec.manifest.get('reference_cohort_version', '-')}")
synthetic = rec.manifest.get("synthetic_data_flag", False)
cols[4].markdown(
    f"**Data**\n\n<span style='color:{CORAL if synthetic else TEAL};font-weight:700;'>"
    f"{'SYNTHETIC' if synthetic else 'PRODUCTION'}</span>",
    unsafe_allow_html=True,
)
if synthetic:
    st.caption(
        "Working example over synthetic NHANES-derived Healthspan and AgelessRx "
        "cohorts. The replication framework, methodology, and verdict logic are "
        "all production-ready - only the data source toggles when Bronze reads "
        "are activated."
    )


# ---------------------------------------------------------------------------
# Verdict callout
# ---------------------------------------------------------------------------
rep = rec.results.get("replication_assessment", {})
verdict = rep.get("verdict", "UNKNOWN")
same_direction = rep.get("same_direction", False)
intervals_overlap = rep.get("intervals_overlap", False)
rel_diff = rep.get("relative_difference_pct")
abs_diff_yrs = rep.get("point_estimate_difference_years", 0)

verdict_colors = {
    "STRONG": (TEAL, "#E6F3F3"),
    "DIRECTIONAL": (GOLD, "#FAF1DA"),
    "FAIL": (CORAL, "#FBE7E1"),
}
vc, vbg = verdict_colors.get(verdict, ("#5A5A6E", "#F5F5F7"))

st.markdown(
    f"""
    <div style='margin-top:18px;padding:22px 24px;background:{vbg};
                border-left:6px solid {vc};border-radius:6px;'>
        <div style='font-size:12px;letter-spacing:1.5px;text-transform:uppercase;
                    color:#5A5A6E;font-weight:600;'>Replication verdict</div>
        <div style='font-size:36px;font-weight:800;color:{vc};margin-top:4px;'>
            {verdict}</div>
        <div style='color:#1A1A2E;margin-top:8px;font-size:14px;'>
            Same direction: <b>{same_direction}</b>  &nbsp;•&nbsp;
            Intervals overlap: <b>{intervals_overlap}</b>  &nbsp;•&nbsp;
            Point-estimate diff: <b>{abs_diff_yrs:+.2f} yrs</b>
            {f' &nbsp;•&nbsp; Relative difference: <b>{rel_diff:.1f}%</b>' if rel_diff is not None else ''}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Side-by-side forest plot
# ---------------------------------------------------------------------------
hs = rec.results.get("healthspan", {})
arx = rec.results.get("agelessrx", {})
hs_ci = hs.get("phenoage_delta_difference", {})
arx_ci = arx.get("phenoage_delta_difference", {})

st.subheader("Headline finding - independently matched estimates")
st.markdown(
    "Each partner cohort was matched separately to NHANES under the same "
    "5-year age band x sex x BMI band x 4:1 matching design. Estimates and "
    "95% intervals are presented side by side."
)


def _two_arm_forest(hs_ci, arx_ci, hs_n, arx_n):
    rows = [
        ("AgelessRx", arx_n, arx_ci.get("point_estimate", 0),
         arx_ci.get("ci_low", 0), arx_ci.get("ci_high", 0), GOLD),
        ("Healthspan", hs_n, hs_ci.get("point_estimate", 0),
         hs_ci.get("ci_low", 0), hs_ci.get("ci_high", 0), NAVY),
    ]
    fig = go.Figure()
    for i, (label, n, pt, lo, hi, color) in enumerate(rows):
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[i, i], mode="lines",
            line=dict(color=color, width=4), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[pt], y=[i], mode="markers",
            marker=dict(symbol="diamond", size=18, color=color,
                        line=dict(color="white", width=2)),
            showlegend=False,
            hovertemplate=f"{label}<br>n={n}<br>Δ=%{{x:.2f}} yrs<extra></extra>",
        ))
    fig.add_vline(x=0, line=dict(color="#1A1A2E", width=1, dash="dash"))
    fig.update_layout(
        title=dict(text="PhenoAge delta difference vs matched NHANES",
                   font=dict(size=15, color=NAVY)),
        xaxis_title="PhenoAge delta difference (years)  - more negative = greater apparent benefit",
        yaxis=dict(
            tickmode="array", tickvals=[0, 1],
            ticktext=[f"AgelessRx (n={arx_n:,})",
                      f"Healthspan (n={hs_n:,})"],
            tickfont=dict(size=14, color=NAVY),
        ),
        height=240,
        margin=dict(l=200, r=40, t=50, b=50),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig


st.plotly_chart(_two_arm_forest(hs_ci, arx_ci, hs.get("n_cohort", 0), arx.get("n_cohort", 0)),
                use_container_width=True)


# Replication-detail metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Healthspan point estimate",
          f"{hs_ci.get('point_estimate', 0):+.2f} yrs",
          f"95% CI [{hs_ci.get('ci_low', 0):+.2f}, {hs_ci.get('ci_high', 0):+.2f}]",
          delta_color="off")
c2.metric("AgelessRx point estimate",
          f"{arx_ci.get('point_estimate', 0):+.2f} yrs",
          f"95% CI [{arx_ci.get('ci_low', 0):+.2f}, {arx_ci.get('ci_high', 0):+.2f}]",
          delta_color="off")
c3.metric("Point-estimate diff", f"{abs_diff_yrs:+.2f} yrs")
c4.metric("Relative difference",
          f"{rel_diff:.1f}%" if rel_diff is not None else "-")


# ---------------------------------------------------------------------------
# 95% CI overlap visualization (interval ribbons on a number line)
# ---------------------------------------------------------------------------
st.subheader("95% confidence interval overlap")
st.markdown(
    "The replication test asks whether the two partners' 95% intervals overlap. "
    "Overlap means the estimates are statistically compatible; no overlap "
    "indicates one partner is producing a meaningfully different effect."
)

overlap_fig = go.Figure()
# Healthspan band
overlap_fig.add_shape(
    type="rect",
    x0=hs_ci.get("ci_low", 0), x1=hs_ci.get("ci_high", 0),
    y0=0.55, y1=0.85,
    fillcolor=NAVY, opacity=0.65, line=dict(width=0),
)
overlap_fig.add_annotation(
    x=hs_ci.get("point_estimate", 0), y=0.70,
    text=f"<b>Healthspan</b>  Δ={hs_ci.get('point_estimate', 0):+.2f}",
    showarrow=False, font=dict(color="white", size=12), bgcolor=NAVY,
)
# AgelessRx band
overlap_fig.add_shape(
    type="rect",
    x0=arx_ci.get("ci_low", 0), x1=arx_ci.get("ci_high", 0),
    y0=0.15, y1=0.45,
    fillcolor=GOLD, opacity=0.75, line=dict(width=0),
)
overlap_fig.add_annotation(
    x=arx_ci.get("point_estimate", 0), y=0.30,
    text=f"<b>AgelessRx</b>  Δ={arx_ci.get('point_estimate', 0):+.2f}",
    showarrow=False, font=dict(color="white", size=12), bgcolor=GOLD,
)
overlap_fig.add_vline(x=0, line=dict(color="#1A1A2E", width=1, dash="dash"))

# x-range padding
xs = [hs_ci.get("ci_low", 0), hs_ci.get("ci_high", 0),
      arx_ci.get("ci_low", 0), arx_ci.get("ci_high", 0), 0]
pad = (max(xs) - min(xs)) * 0.15
overlap_fig.update_layout(
    xaxis=dict(title="PhenoAge delta difference (years)",
               range=[min(xs) - pad, max(xs) + pad], showgrid=True, zeroline=False),
    yaxis=dict(visible=False, range=[0, 1]),
    height=280, plot_bgcolor="white", paper_bgcolor="white",
    margin=dict(l=20, r=20, t=20, b=50),
)
st.plotly_chart(overlap_fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Class-aligned subgroups
# ---------------------------------------------------------------------------
class_compare = rec.results.get("by_intervention_class", {})
if class_compare:
    st.subheader("Class-aligned subgroup replication")
    st.markdown(
        "Where both partners run a comparable intervention class, the page "
        "shows the within-class replication. Classes are not always 1:1 across "
        "partner formularies, so closest analogous classes are paired."
    )
    rows = []
    for pair_key, d in class_compare.items():
        hs_pair, arx_pair = pair_key.split("__vs__")
        hs_pci = d.get("healthspan_ci", {})
        arx_pci = d.get("agelessrx_ci", {})
        rows.append(dict(
            HS_class=hs_pair,
            ARx_class=arx_pair,
            HS_n=d.get("n_healthspan", 0),
            ARx_n=d.get("n_agelessrx", 0),
            HS_point=round(hs_pci.get("point_estimate", 0), 2),
            HS_CI_lo=round(hs_pci.get("ci_low", 0), 2),
            HS_CI_hi=round(hs_pci.get("ci_high", 0), 2),
            ARx_point=round(arx_pci.get("point_estimate", 0), 2),
            ARx_CI_lo=round(arx_pci.get("ci_low", 0), 2),
            ARx_CI_hi=round(arx_pci.get("ci_high", 0), 2),
            Intervals_overlap=d.get("intervals_overlap", False),
        ))
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Methodology box
# ---------------------------------------------------------------------------
methods = rec.manifest.get("methods", {})
with st.expander("Methodology and replication criterion"):
    st.markdown(
        "- **PhenoAge:** Levine 2018, computed from the nine biomarker panel "
        "in each partner's labs.\n"
        "- **Matching:** Each partner cohort matched independently to NHANES "
        "using 5-year age band x sex x BMI band, 4:1 ratio.\n"
        "- **Uncertainty:** Monte Carlo 10,000 iterations, 95% CI per partner.\n"
        "- **Replication criterion:** (1) same direction, (2) overlapping 95% "
        "CIs, (3) relative point-estimate difference < 30% qualifies as STRONG; "
        "same direction only qualifies as DIRECTIONAL; otherwise FAIL.\n"
    )
    if methods:
        st.json(methods)


st.markdown(
    f"""
    <div style='margin-top:30px;padding:12px 16px;background:#F5F5F7;
                border-left:3px solid {NAVY};border-radius:4px;font-size:12px;
                color:#5A5A6E;'>
        Strategic note: this is the credential the pharma analytics buyer asks
        for first. The Inexion Longevity Registry is the only commercial source
        that can produce independent multi-partner replication on longevity
        intervention effects, because the longitudinal lab panel does not exist
        in claims-derived RWD platforms.
    </div>
    """,
    unsafe_allow_html=True,
)
