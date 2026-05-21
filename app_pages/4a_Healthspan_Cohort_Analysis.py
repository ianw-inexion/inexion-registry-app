"""
Healthspan Cohort Analysis
==========================

Surfaces the six Healthspan hypothesis runs in one partner-facing page.

  H1  Cohort-level PhenoAge advantage (unadjusted + lifestyle-adjusted)
  H2  Intervention-class segmented response (with BH FDR)
  H3  Time-to-response trajectory
  H4  Lifestyle-adjusted PhenoAge attribution
  H5  Retention bias quantification (ITT vs as-treated)
  H6  Projected 10-year ASCVD risk reduction

Each hypothesis lives in its own tab. The page reads the latest run per
hypothesis from analytics/runs/ via the shared run_loader helper. When the
underlying data is synthetic (today) a banner makes that clear; when partner
Bronze reads are wired up the page surface stays identical.
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import NAVY, GOLD, CORAL, TEAL, BRAND_COLORWAY
from analytics.lib.run_loader import latest_run, format_ran_at

st.set_page_config(page_title="Healthspan Cohort Analysis - INEXION Registry", layout="wide")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Longevity Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            Healthspan Cohort Analysis</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Six pre-registered hypotheses on the Healthspan longitudinal cohort,
            matched against NHANES reference.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Provenance strip
# ---------------------------------------------------------------------------
def _provenance_strip(record):
    if record is None:
        st.info("No run found for this hypothesis. Execute the script under analytics/hypotheses/ to populate.")
        return
    cols = st.columns([1.5, 1.5, 1, 1.5, 1])
    cols[0].markdown(f"**Run ID**\n\n`{record.run_id}`")
    cols[1].markdown(f"**Ran at**\n\n{format_ran_at(record.ran_at)}")
    cols[2].markdown(f"**Commit**\n\n`{record.manifest.get('code_commit_hash', '?')[:12]}`")
    cols[3].markdown(f"**Reference**\n\n{record.manifest.get('reference_cohort_version', '-')}")
    synthetic = record.manifest.get("synthetic_data_flag", False)
    cols[4].markdown(
        f"**Data**\n\n<span style='color:{CORAL if synthetic else TEAL};font-weight:700;'>"
        f"{'SYNTHETIC' if synthetic else 'PRODUCTION'}</span>",
        unsafe_allow_html=True,
    )
    if synthetic:
        st.caption(
            "Working example over a synthetic NHANES-derived cohort. Headline "
            "values will refresh against the Healthspan Bronze read once "
            "DUA-governed ingestion is active."
        )


# ---------------------------------------------------------------------------
# Forest-plot helper
# ---------------------------------------------------------------------------
def _forest_plot(rows, title, x_title="PhenoAge delta difference (years)"):
    """rows: list of (label, n, point, lo, hi, significant_flag).
    Negative point = cohort younger than reference = good."""
    rows = list(reversed(rows))
    fig = go.Figure()
    for i, (label, n, pt, lo, hi, sig) in enumerate(rows):
        color = NAVY if sig else "#9BA0A8"
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[i, i],
            mode="lines",
            line=dict(color=color, width=3),
            showlegend=False,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[pt], y=[i],
            mode="markers",
            marker=dict(symbol="diamond", size=14, color=color,
                        line=dict(color="white", width=2)),
            showlegend=False,
            hovertemplate=f"{label}<br>n={n}<br>Δ=%{{x:.2f}} yrs<extra></extra>",
        ))
    fig.add_vline(x=0, line=dict(color="#1A1A2E", width=1, dash="dash"))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=NAVY)),
        xaxis_title=x_title,
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(len(rows))),
            ticktext=[f"{r[0]} (n={r[1]})" for r in rows],
            tickfont=dict(size=12),
        ),
        height=80 + 45 * len(rows),
        margin=dict(l=200, r=40, t=50, b=40),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_h1, tab_h2, tab_h3, tab_h4, tab_h5, tab_h6 = st.tabs([
    "H1 - Cohort effect",
    "H2 - By intervention class",
    "H3 - Time-to-response",
    "H4 - Lifestyle adjusted",
    "H5 - Retention bias",
    "H6 - ASCVD risk",
])


# H1 -----------------------------------------------------------------------
with tab_h1:
    rec = latest_run("HEALTHSPAN_H1")
    st.subheader("H1 - Cohort-level PhenoAge advantage")
    st.markdown(
        "**Hypothesis.** Healthspan patients on any active protocol for ≥ 12 "
        "months show a PhenoAge delta meaningfully more negative than a matched "
        "NHANES reference. Effect should survive lifestyle adjustment via IPW."
    )
    _provenance_strip(rec)
    if rec is not None:
        r = rec.results
        unadj = r.get("unadjusted_delta_difference", {})
        adj = r.get("lifestyle_adjusted_delta_difference", {})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cohort n", f"{r.get('n_cohort', 0):,}")
        c2.metric("Matched ref n", f"{r.get('n_matched_reference', 0):,}")
        c3.metric(
            "Unadjusted Δ (yrs)",
            f"{unadj.get('point_estimate', 0):+.2f}",
            f"95% CI [{unadj.get('ci_low', 0):+.2f}, {unadj.get('ci_high', 0):+.2f}]",
            delta_color="off",
        )
        c4.metric(
            "Lifestyle-adjusted Δ",
            f"{adj.get('point_estimate', 0):+.2f}",
            f"95% CI [{adj.get('ci_low', 0):+.2f}, {adj.get('ci_high', 0):+.2f}]",
            delta_color="off",
        )
        rows = [
            ("Unadjusted (cohort vs matched NHANES)", r.get("n_cohort", 0),
             unadj.get("point_estimate", 0), unadj.get("ci_low", 0), unadj.get("ci_high", 0),
             unadj.get("p_value", 1) < 0.05),
            ("Lifestyle-adjusted (IPW: BMI x smoking x activity)", r.get("n_cohort", 0),
             adj.get("point_estimate", 0), adj.get("ci_low", 0), adj.get("ci_high", 0),
             adj.get("p_value", 1) < 0.05),
        ]
        st.plotly_chart(_forest_plot(rows, "Cohort PhenoAge advantage - point estimates with 95% CI"),
                        use_container_width=True)


# H2 -----------------------------------------------------------------------
with tab_h2:
    rec = latest_run("HEALTHSPAN_H2")
    st.subheader("H2 - PhenoAge response by intervention class")
    st.markdown(
        "**Hypothesis.** Within the Healthspan cohort, effect size varies "
        "meaningfully across protocol classes (HRT, GLP-1, NAD precursor, "
        "multi-modal, peptides). Class-level effects are reported with "
        "Benjamini-Hochberg FDR correction."
    )
    _provenance_strip(rec)
    if rec is not None:
        classes = rec.results.get("by_protocol_class", {})
        rows = []
        for name in sorted(classes.keys()):
            d = classes[name]
            rows.append((
                name, d.get("n", 0), d.get("point_estimate", 0),
                d.get("ci_low", 0), d.get("ci_high", 0),
                bool(d.get("significant_after_bh_fdr", False)),
            ))
        st.plotly_chart(_forest_plot(rows, "PhenoAge delta difference vs matched NHANES, by class"),
                        use_container_width=True)
        df = pd.DataFrame([
            dict(
                Class=name,
                n=d["n"],
                Point=round(d["point_estimate"], 2),
                CI_low=round(d["ci_low"], 2),
                CI_high=round(d["ci_high"], 2),
                p=round(d["p_value"], 4),
                BH_FDR_sig=d["significant_after_bh_fdr"],
            )
            for name, d in sorted(classes.items())
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)


# H3 -----------------------------------------------------------------------
with tab_h3:
    rec = latest_run("HEALTHSPAN_H3")
    st.subheader("H3 - Time-to-response trajectory")
    st.markdown(
        "**Hypothesis.** PhenoAge improvement follows a detectable trajectory "
        "across 0, 6, 12, 18, 24-month visits. Time-to-first-detectable-improvement "
        "and plateau month are surfaced where present."
    )
    _provenance_strip(rec)
    if rec is not None:
        traj = pd.DataFrame(rec.results.get("trajectory", []))
        if not traj.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=traj["timepoint_month"], y=traj["mean_delta"],
                mode="lines+markers",
                line=dict(color=NAVY, width=3),
                marker=dict(size=11, color=GOLD,
                            line=dict(color=NAVY, width=2)),
                name="Mean PhenoAge Δ",
            ))
            fig.add_trace(go.Scatter(
                x=traj["timepoint_month"], y=traj["median_delta"],
                mode="lines+markers",
                line=dict(color=TEAL, width=2, dash="dash"),
                marker=dict(size=8, color=TEAL),
                name="Median PhenoAge Δ",
            ))
            fig.add_hline(y=0, line=dict(color="#9BA0A8", dash="dot"))
            fig.update_layout(
                xaxis_title="Months on protocol",
                yaxis_title="PhenoAge delta (years)",
                height=420, plot_bgcolor="white", paper_bgcolor="white",
                colorway=BRAND_COLORWAY,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

            c1, c2 = st.columns(2)
            ttdi = rec.results.get("time_to_detectable_improvement_months")
            plat = rec.results.get("plateau_month")
            c1.metric("Time to detectable improvement",
                      f"{ttdi} months" if ttdi is not None else "not detected")
            c2.metric("Plateau month",
                      f"{plat}" if plat is not None else "no plateau in window")

            st.dataframe(
                traj.round(3),
                use_container_width=True, hide_index=True,
            )


# H4 -----------------------------------------------------------------------
with tab_h4:
    rec = latest_run("HEALTHSPAN_H4")
    st.subheader("H4 - Lifestyle-adjusted attribution")
    st.markdown(
        "**Hypothesis.** After IPW adjustment for BMI, smoking, and physical "
        "activity, the protocol effect remains at least 70% of its unadjusted "
        "value. Heterogeneity by favorable vs unfavorable baseline lifestyle "
        "is also surfaced."
    )
    _provenance_strip(rec)
    if rec is not None:
        r = rec.results
        unadj = r.get("unadjusted_delta_difference", {})
        adj = r.get("lifestyle_adjusted_delta_difference", {})
        retained = r.get("attribution_retained_fraction")
        c1, c2, c3 = st.columns(3)
        c1.metric("Unadjusted Δ", f"{unadj.get('point_estimate', 0):+.2f} yrs")
        c2.metric("IPW-adjusted Δ", f"{adj.get('point_estimate', 0):+.2f} yrs")
        c3.metric("Effect retained after lifestyle adj.",
                  f"{retained * 100:.1f}%" if retained is not None else "-")

        rows = [
            ("Unadjusted", r.get("n_cohort", 0),
             unadj.get("point_estimate", 0), unadj.get("ci_low", 0), unadj.get("ci_high", 0),
             unadj.get("p_value", 1) < 0.05),
            ("Lifestyle-adjusted (IPW)", r.get("n_cohort", 0),
             adj.get("point_estimate", 0), adj.get("ci_low", 0), adj.get("ci_high", 0),
             adj.get("p_value", 1) < 0.05),
        ]
        by_life = r.get("by_baseline_lifestyle", {})
        for label, key in [("Favorable baseline lifestyle", "favorable_baseline"),
                           ("Unfavorable baseline lifestyle", "unfavorable_baseline")]:
            d = by_life.get(key, {})
            if d:
                rows.append((
                    label, d.get("n", 0),
                    d.get("point_estimate", 0), d.get("ci_low", 0), d.get("ci_high", 0),
                    d.get("p_value", 1) < 0.05,
                ))
        st.plotly_chart(_forest_plot(rows, "Lifestyle adjustment + baseline-lifestyle heterogeneity"),
                        use_container_width=True)


# H5 -----------------------------------------------------------------------
with tab_h5:
    rec = latest_run("HEALTHSPAN_H5")
    st.subheader("H5 - Retention as a confounding signal")
    st.markdown(
        "**Hypothesis.** Patients who drop off within 6 months differ "
        "systematically from retained patients at baseline. Naive as-treated "
        "estimates that exclude drop-offs inflate the apparent protocol "
        "effect by ~20-35%. This is the defensibility-critical metric for "
        "any partner conversation."
    )
    _provenance_strip(rec)
    if rec is not None:
        r = rec.results
        itt = r.get("intention_to_treat", {})
        at = r.get("as_treated_retained_only", {})
        bias_pct = r.get("bias_magnitude_pct_of_itt")
        bc = r.get("baseline_compare", {})

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Retention rate",
                  f"{bc.get('retention_rate', 0) * 100:.1f}%")
        c2.metric("ITT Δ (all enrolled)", f"{itt.get('point_estimate', 0):+.2f} yrs")
        c3.metric("As-treated Δ (retained only)", f"{at.get('point_estimate', 0):+.2f} yrs")
        c4.metric("Bias magnitude vs ITT",
                  f"{bias_pct:+.1f}%" if bias_pct is not None else "-")

        rows = [
            ("ITT - all enrolled patients", r.get("n_cohort_total", 0),
             itt.get("point_estimate", 0), itt.get("ci_low", 0), itt.get("ci_high", 0),
             itt.get("p_value", 1) < 0.05),
            ("As-treated - retained patients only", bc.get("n_retained", 0),
             at.get("point_estimate", 0), at.get("ci_low", 0), at.get("ci_high", 0),
             at.get("p_value", 1) < 0.05),
        ]
        st.plotly_chart(_forest_plot(rows, "ITT vs as-treated estimates"),
                        use_container_width=True)

        st.markdown("**Baseline characteristics: dropoffs vs retained**")
        comp = pd.DataFrame([
            dict(Metric="n", Dropoffs=bc.get("n_dropoffs", 0),
                 Retained=bc.get("n_retained", 0)),
            dict(Metric="Mean baseline PhenoAge Δ",
                 Dropoffs=round(bc.get("mean_phenoage_delta_baseline_dropoffs", 0), 2),
                 Retained=round(bc.get("mean_phenoage_delta_baseline_retained", 0), 2)),
            dict(Metric="Mean BMI",
                 Dropoffs=round(bc.get("mean_bmi_dropoffs", 0), 1),
                 Retained=round(bc.get("mean_bmi_retained", 0), 1)),
            dict(Metric="% current smokers",
                 Dropoffs=round(bc.get("pct_current_smokers_dropoffs", 0), 1),
                 Retained=round(bc.get("pct_current_smokers_retained", 0), 1)),
        ])
        st.dataframe(comp, use_container_width=True, hide_index=True)
        st.caption(r.get("interpretation", ""))


# H6 -----------------------------------------------------------------------
with tab_h6:
    rec = latest_run("HEALTHSPAN_H6")
    st.subheader("H6 - Projected 10-year ASCVD risk reduction")
    st.markdown(
        "**Hypothesis.** Patients aged 50+ on cardiometabolic-active protocols "
        "(HRT, GLP-1, multi-modal) show a 10-year ASCVD risk (Goff 2014 Pooled "
        "Cohort Equations) that is 15-30% lower than baseline-matched NHANES "
        "participants at 12-month follow-up."
    )
    _provenance_strip(rec)
    if rec is not None:
        r = rec.results
        cohort_rk = r.get("mean_ascvd_10yr_risk_cohort", 0) * 100
        ref_rk = r.get("mean_ascvd_10yr_risk_reference", 0) * 100
        rrr = r.get("relative_risk_reduction_pct", 0)
        ard = r.get("absolute_risk_difference", {})
        n_co = r.get("n_cohort_cardiometabolic_50plus", 0)
        n_ref = r.get("n_matched_reference", 0)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("50+ cardiometabolic subcohort n", f"{n_co:,}")
        c2.metric("Mean 10-yr ASCVD risk (cohort)", f"{cohort_rk:.2f}%")
        c3.metric("Mean 10-yr ASCVD risk (reference)", f"{ref_rk:.2f}%")
        c4.metric("Relative risk reduction", f"{rrr:.1f}%")

        # Bar chart comparing cohort vs reference
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Healthspan 50+ cardiometabolic", "Matched NHANES reference"],
            y=[cohort_rk, ref_rk],
            marker_color=[GOLD, NAVY],
            text=[f"{cohort_rk:.2f}%", f"{ref_rk:.2f}%"],
            textposition="outside",
        ))
        fig.update_layout(
            title="Mean projected 10-year ASCVD risk",
            yaxis_title="Mean 10-yr ASCVD risk (%)",
            height=380, plot_bgcolor="white", paper_bgcolor="white",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            f"**Absolute risk difference:** {ard.get('point_estimate', 0) * 100:+.2f} "
            f"percentage points  •  95% CI [{ard.get('ci_low', 0) * 100:+.2f}, "
            f"{ard.get('ci_high', 0) * 100:+.2f}]  •  p = {ard.get('p_value', 1):.4f}"
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div style='margin-top:30px;padding:12px 16px;background:#F5F5F7;
                border-left:3px solid {NAVY};border-radius:4px;font-size:12px;
                color:#5A5A6E;'>
        Each tab is generated from analytics/runs/HEALTHSPAN_H&lt;N&gt;_*. Re-run
        the script under analytics/hypotheses/ to refresh. When Healthspan
        Bronze ingestion is active, generate_healthspan_cohort gets swapped
        for the bronze read; the page surface does not change.
    </div>
    """,
    unsafe_allow_html=True,
)
