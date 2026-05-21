"""
Partner-facing hypothesis report template.

Renders an analysis run (manifest + results) into a branded HTML document
suitable for sharing with data partners (Healthspan, AgelessRx) and for
inclusion in the INEXION data room.

Brand spec follows inexion-brand-guide:
    Inter throughout, Navy #0D1B3E, Gold #C9941A,
    Heading Blue #2E74B5 / #1F4D78, light gray section backgrounds.
"""

from __future__ import annotations

from datetime import datetime
from html import escape


NAVY = "#0D1B3E"
GOLD = "#C9941A"
HEAD_BLUE = "#2E74B5"
H3_BLUE = "#1F4D78"
DARK_TEXT = "#1A1A2E"
LIGHT_GRAY = "#F5F7FA"
CALLOUT_BG = "#FDF8EE"


def _fmt_num(x, digits=2):
    try:
        return f"{float(x):+0.{digits}f}"
    except Exception:
        return str(x)


def _fmt_p(p):
    try:
        p = float(p)
    except Exception:
        return str(p)
    if p < 0.001:
        return "< 0.001"
    return f"{p:.3f}"


def render_estimate_row(label: str, est: dict) -> str:
    return f"""
    <tr>
      <td class="label">{escape(label)}</td>
      <td class="num">{_fmt_num(est.get('point_estimate'))} yrs</td>
      <td class="num">[{_fmt_num(est.get('ci_low'))}, {_fmt_num(est.get('ci_high'))}]</td>
      <td class="num">{_fmt_p(est.get('p_value'))}</td>
      <td class="num">{int(est.get('iterations', 0)):,}</td>
    </tr>
    """


def render_report(manifest: dict, results: dict) -> str:
    """
    Render a complete partner-facing HTML report for a single analysis run.
    Inputs are the inex_analysis_run-shaped manifest dict and the results dict
    produced by the analytics script.
    """
    hyp_id = results.get("hypothesis_id", manifest.get("hypothesis_id", "—"))
    hyp_title = results.get("hypothesis_title", "Hypothesis Result")
    cohort_def = manifest.get("cohort_definition", {})
    methods = manifest.get("methods", {})
    synthetic = manifest.get("synthetic_data_flag", False)
    notes = manifest.get("notes", []) or []
    ran_at = manifest.get("ran_at", datetime.utcnow().isoformat())
    run_id = manifest.get("run_id", "—")
    ref_version = manifest.get("reference_cohort_version", "—")

    unadjusted = results.get("unadjusted_delta_difference", {})
    adjusted = results.get("lifestyle_adjusted_delta_difference", {})
    by_protocol = results.get("by_protocol_class", {})

    protocol_rows = "".join(
        f"<tr><td class='label'>{escape(k)}</td>"
        f"<td class='num'>{v['n']:,}</td>"
        f"<td class='num'>{_fmt_num(v['mean_delta_cohort'])} yrs</td></tr>"
        for k, v in by_protocol.items()
    ) or "<tr><td colspan='3' class='label'>Insufficient subgroup sample sizes for stratification.</td></tr>"

    cohort_rows = "".join(
        f"<tr><td class='label'>{escape(str(k).replace('_',' ').title())}</td>"
        f"<td>{escape(str(v))}</td></tr>"
        for k, v in cohort_def.items()
    )

    methods_rows = "".join(
        f"<tr><td class='label'>{escape(str(k).replace('_',' ').title())}</td>"
        f"<td>{escape(str(v))}</td></tr>"
        for k, v in methods.items()
    )

    synthetic_banner = ""
    if synthetic:
        synthetic_banner = """
        <div class="callout synthetic">
          <strong>SYNTHETIC DATA — INTERNAL ONLY.</strong>
          This report was generated against a stand-in cohort synthesized from public
          NHANES data with a simulated treatment-effect perturbation. The numbers
          illustrate the analytical pipeline; they do not represent real partner data.
          This banner appears only when manifest.synthetic_data_flag is true.
        </div>
        """

    note_lis = "\n".join(f"<li>{escape(n)}</li>" for n in notes)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>INEXION — {escape(hyp_id)} — {escape(hyp_title)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Inter', -apple-system, sans-serif;
    color: {DARK_TEXT};
    margin: 0; padding: 0;
    background: #ffffff;
    font-size: 14px;
    line-height: 1.55;
  }}
  .page {{ max-width: 880px; margin: 0 auto; padding: 40px 56px; }}
  header.brand {{
    border-bottom: 2px solid {GOLD};
    padding-bottom: 16px; margin-bottom: 28px;
    display: flex; align-items: flex-end; justify-content: space-between;
  }}
  .wordmark {{
    font-weight: 700; font-size: 22px; letter-spacing: 0.06em;
    color: {NAVY};
  }}
  .meta {{ color: #666666; font-size: 11px; text-align: right; }}
  h1 {{
    font-size: 24px; color: {HEAD_BLUE}; font-weight: 700;
    margin: 32px 0 8px 0;
  }}
  h2 {{
    font-size: 18px; color: {HEAD_BLUE}; font-weight: 700;
    margin: 28px 0 8px 0;
  }}
  h3 {{
    font-size: 14px; color: {H3_BLUE}; font-weight: 700;
    margin: 20px 0 6px 0;
  }}
  .section-label {{
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
    color: {NAVY}; text-transform: uppercase;
    border-bottom: 2px solid {GOLD}; padding-bottom: 4px;
    margin: 36px 0 12px 0;
  }}
  .callout {{
    background: {CALLOUT_BG}; border-left: 4px solid {GOLD};
    padding: 12px 16px; margin: 16px 0;
    font-style: italic;
  }}
  .callout.synthetic {{ font-style: normal; }}
  table {{
    width: 100%; border-collapse: collapse; margin: 12px 0 20px 0;
    font-size: 13px;
  }}
  th {{
    background: {NAVY}; color: #ffffff; font-weight: 700;
    text-align: left; padding: 8px 10px;
  }}
  td {{
    padding: 8px 10px; border: 1px solid #D0D5E0;
    vertical-align: top;
  }}
  tr:nth-child(even) td {{ background: {LIGHT_GRAY}; }}
  td.label {{ background: {LIGHT_GRAY}; font-weight: 700; color: {NAVY}; width: 36%; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  ul.notes li {{ margin-bottom: 4px; }}
  footer.brand {{
    border-top: 2px solid {GOLD}; margin-top: 48px; padding-top: 12px;
    color: #888888; font-size: 11px;
    display: flex; justify-content: space-between;
  }}
</style>
</head>
<body>
<div class="page">

  <header class="brand">
    <div class="wordmark">INEXION</div>
    <div class="meta">
      Hypothesis Result Report<br>
      Run {escape(run_id)} &middot; {escape(ran_at)}
    </div>
  </header>

  <h1>{escape(hyp_title)}</h1>
  <div class="meta" style="text-align:left; margin-top:-4px;">
    {escape(hyp_id)} &middot; Reference: {escape(ref_version)}
  </div>

  {synthetic_banner}

  <div class="section-label">01 &middot; Cohort Definition</div>
  <table>
    <tbody>{cohort_rows}</tbody>
  </table>

  <div class="section-label">02 &middot; Methods</div>
  <table>
    <tbody>{methods_rows}</tbody>
  </table>

  <div class="section-label">03 &middot; Primary Result</div>
  <h3>PhenoAge delta: cohort vs matched reference</h3>
  <table>
    <thead>
      <tr><th>Estimate</th><th>Point</th><th>95% CI</th><th>p-value</th><th>MC iterations</th></tr>
    </thead>
    <tbody>
      {render_estimate_row("Unadjusted Δ (cohort − matched reference)", unadjusted)}
      {render_estimate_row("IPW lifestyle-adjusted Δ", adjusted)}
    </tbody>
  </table>

  <div class="section-label">04 &middot; Stratified Results by Protocol Class</div>
  <table>
    <thead>
      <tr><th>Protocol class</th><th>n</th><th>Mean PhenoAge Δ</th></tr>
    </thead>
    <tbody>
      {protocol_rows}
    </tbody>
  </table>

  <div class="section-label">05 &middot; Notes and Limitations</div>
  <ul class="notes">
    {note_lis}
    <li>Matching strategy: 5-year age band × sex × BMI band. Cells with fewer than 3 reference patients excluded from the primary estimate.</li>
    <li>Multiple-comparison correction (BH FDR at 0.05) applies when multiple hypotheses are reported together; this single-hypothesis report does not invoke the correction.</li>
    <li>The Healthspan cohort definition requires &ge; 12 months of protocol exposure. Patients below the threshold are excluded.</li>
  </ul>

  <div class="section-label">06 &middot; Acknowledgments</div>
  <p>
    Data sources: Health and Retirement Study (when applied as a secondary reference);
    National Health and Nutrition Examination Survey (NHANES) cycles 1999–2018,
    Centers for Disease Control and Prevention, National Center for Health Statistics.
    Analysis performed by INEXION Holdings LLC under IRB umbrella protocol.
  </p>

  <footer class="brand">
    <div>INEXION Holdings LLC &middot; Confidential &middot; Hypothesis Result Report</div>
    <div>Generated {escape(ran_at)}</div>
  </footer>

</div>
</body>
</html>
"""
