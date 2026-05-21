"""
AgelessRx Cohort Analysis
=========================

Surfaces the three AgelessRx hypothesis runs available in Tier-1/2 today.

  H1  Multi-modal protocol PhenoAge advantage
  H2  Rapamycin real-world signal vs PEARL trial reference
  H6  AgelessRx arm of the cross-partner replication
      (full cross-partner view lives in 4c_Cross_Partner_View)

Additional AgelessRx hypotheses (H3, H4, H5, H7, H8) require real partner
data and will appear here once Bronze ingestion is active.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import NAVY, GOLD, CORAL, TEAL, BRAND_COLORWAY
from analytics.lib.run_loader import latest_run, format_ran_at

st.set_page_config(page_title="AgelessRx Cohort Analysis - INEXION Registry", layout="wide")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div style='padding:18px 24px;background:{NAVY};border-radius:8px;margin-bottom:20px;'>
        <div style='color:{GOLD};font-size:12px;letter-spacing:2px;
                    text-transform:uppercase;font-weight:600;'>INEXION Longevity Registry</div>
        <div style='color:white;font-size:26px;font-weight:700;margin-top:4px;'>
            AgelessRx Cohort Analysis</div>
        <div style='color:#C9CBD4;font-size:13px;margin-top:6px;'>
            Pre-registered hypotheses against the AgelessRx longitudinal cohort,
            including the rapamycin signal vs the PEARL RCT benchmark.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


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
            "Working example over a synthetic NHANES-derived cohort. "
            "Headline values will refresh against the AgelessRx Bronze read "
            "once the partner DUA is countersigned and ingestion is live."
        )


def _forest_plot(rows, title, x_title="PhenoAge delta difference (years)"):
    rows = list(reversed(rows))
    fig = go.Figure()
    for i, (label, n, pt, lo, hi, sig) in enumerate(rows):
        color = NAVY if sig else "#9BA0A8"
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[i, i], mode="lines",
            line=dict(color=color, width=3), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[pt], y=[i], mode="markers",
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
        margin=dict(l=240, r=40, t=50, b=40),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_h1, tab_h2, tab_h6 = st.tabs([
    "H1 - Multi-modal advantage",
    "H2 - Rapamycin vs PEARL",
    "H6 - AgelessRx arm",
])


# H1 -----------------------------------------------------------------------
with tab_h1:
    rec = latest_run("AGELESSRX_H1")
    st.subheader("H1 - Multi-modal protocol PhenoAge advantage")
    st.markdown(
        "**Hypothesis.** Patients on three or more concurrent active protocols "
        "show a PhenoAge delta that is 3-6 years more negative than matched "
        "NHANES controls - a larger effect than any single-protocol arm."
    )
    _provenance_strip(rec)
    if rec is not None:
        r = rec.results
        mm = r.get("multimodal_vs_nhanes_delta_difference", {})
        sa = r.get("single_arm_vs_nhanes_delta_difference", {})
        direct = r.get("multimodal_vs_single_arm_delta_difference", {})

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Multi-modal n", f"{r.get('n_multimodal', 0):,}")
        c2.metric("Single-arm n", f"{r.get('n_single_arm', 0):,}")
        c3.metric("Multi-modal Δ vs NHANES", f"{mm.get('point_estimate', 0):+.2f} yrs")
        c4.metric("Direct: multi-modal vs single-arm",
                  f"{direct.get('point_estimate', 0):+.2f} yrs")

        rows = [
            ("Multi-modal (≥3 protocols) vs NHANES", r.get("n_multimodal", 0),
             mm.get("point_estimate", 0), mm.get("ci_low", 0), mm.get("ci_high", 0),
             mm.get("p_value", 1) < 0.05),
            ("Single-arm vs NHANES", r.get("n_single_arm", 0),
             sa.get("point_estimate", 0), sa.get("ci_low", 0), sa.get("ci_high", 0),
             sa.get("p_value", 1) < 0.05),
            ("Direct: multi-modal vs single-arm", r.get("n_multimodal", 0),
             direct.get("point_estimate", 0), direct.get("ci_low", 0), direct.get("ci_high", 0),
             direct.get("p_value", 1) < 0.05),
        ]
        st.plotly_chart(_forest_plot(rows, "Multi-modal vs single-arm: PhenoAge effect"),
                        use_container_width=True)


# H2 -----------------------------------------------------------------------
with tab_h2:
    rec = latest_run("AGELESSRX_H2")
    st.subheader("H2 - Rapamycin real-world signal vs PEARL trial")
    st.markdown(
        "**Hypothesis.** Real-world rapamycin users at matched dose produce a "
        "PhenoAge delta directionally consistent with PEARL (Aging, May 2025). "
        "Effect-size attenuation in real-world use is no greater than 40% "
        "relative to the RCT estimate. PEARL reference is placeholder until "
        "published estimates are wired in."
    )
    _provenance_strip(rec)
    if rec is not None:
        r = rec.results
        rwe = r.get("real_world_phenoage_delta_difference", {})
        pearl_pt = r.get("pearl_published_phenoage_delta_yrs", 0)
        atten = r.get("attenuation_pct_vs_pearl")
        within = r.get("within_40pct_attenuation_threshold")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rapamycin n", f"{r.get('n_rapamycin_cohort', 0):,}")
        c2.metric("Real-world Δ", f"{rwe.get('point_estimate', 0):+.2f} yrs")
        c3.metric("PEARL published Δ", f"{pearl_pt:+.2f} yrs")
        c4.metric("Attenuation vs PEARL",
                  f"{atten:+.1f}%" if atten is not None else "-",
                  f"Within 40% threshold: {within}" if within is not None else "")

        # Real-world vs PEARL
        rows = [
            ("Real-world (AgelessRx rapamycin users)", r.get("n_rapamycin_cohort", 0),
             rwe.get("point_estimate", 0), rwe.get("ci_low", 0), rwe.get("ci_high", 0),
             rwe.get("p_value", 1) < 0.05),
            ("PEARL trial published effect", 0, pearl_pt, pearl_pt, pearl_pt, True),
        ]
        st.plotly_chart(_forest_plot(rows, "Real-world rapamycin signal vs PEARL benchmark"),
                        use_container_width=True)

        st.markdown("**Dose-response stratification**")
        by_dose = r.get("by_dose", {})
        if by_dose:
            dose_rows = []
            for dose_key in sorted(by_dose.keys(), key=lambda k: float(k.split("_")[0])):
                d = by_dose[dose_key]
                dose_rows.append((
                    dose_key.replace("_", " "), d.get("n", 0),
                    d.get("point_estimate", 0), d.get("ci_low", 0), d.get("ci_high", 0),
                    d.get("p_value", 1) < 0.05,
                ))
            st.plotly_chart(_forest_plot(dose_rows, "PhenoAge delta by rapamycin dose"),
                            use_container_width=True)

        st.caption(
            "PEARL reference values in this build are placeholders. The "
            "attenuation calculation will update automatically when the "
            "published Aging 2025 estimates are pinned in the script."
        )


# H6 ----------------------------------------------------------------------
with tab_h6:
    rec = latest_run("AGELESSRX_H6")
    st.subheader("H6 - AgelessRx arm of the cross-partner replication")
    st.markdown(
        "**Hypothesis.** When the AgelessRx cohort is independently matched "
        "to NHANES under the same methodology used for the Healthspan arm, "
        "the resulting PhenoAge delta is directionally consistent with the "
        "Healthspan finding, with overlapping 95% confidence intervals. The "
        "full side-by-side replication is on the Cross-Partner View page."
    )
    _provenance_strip(rec)
    if rec is not None:
        arx = rec.results.get("agelessrx", {})
        ci = arx.get("phenoage_delta_difference", {})

        c1, c2, c3 = st.columns(3)
        c1.metric("AgelessRx cohort n", f"{arx.get('n_cohort', 0):,}")
        c2.metric("Matched NHANES reference n",
                  f"{arx.get('n_matched_reference', 0):,}")
        c3.metric("PhenoAge Δ vs NHANES",
                  f"{ci.get('point_estimate', 0):+.2f} yrs",
                  f"95% CI [{ci.get('ci_low', 0):+.2f}, {ci.get('ci_high', 0):+.2f}]",
                  delta_color="off")

        rows = [
            ("AgelessRx cohort vs matched NHANES", arx.get("n_cohort", 0),
             ci.get("point_estimate", 0), ci.get("ci_low", 0), ci.get("ci_high", 0),
             ci.get("p_value", 1) < 0.05),
        ]
        st.plotly_chart(_forest_plot(rows, "AgelessRx arm - PhenoAge delta vs matched NHANES"),
                        use_container_width=True)
        st.info("See **Cross-Partner View** for the full Healthspan + AgelessRx side-by-side replication.")


st.markdown(
    f"""
    <div style='margin-top:30px;padding:12px 16px;background:#F5F5F7;
                border-left:3px solid {NAVY};border-radius:4px;font-size:12px;
                color:#5A5A6E;'>
        AgelessRx H3, H4, H5, H7, and H8 are blocked on real partner data
        ingestion and will surface here automatically once a corresponding
        run is written to analytics/runs/.
    </div>
    """,
    unsafe_allow_html=True,
)
