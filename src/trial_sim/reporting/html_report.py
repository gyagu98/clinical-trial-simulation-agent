"""HTML report generation for clinical trial simulation runs."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from html import escape
from typing import Any

from ..simulation.scenarios import TrialScenario
from .sensitivity import generate_sensitivity_plots, run_sensitivity_grid


def generate_html_report(
    sim_result: dict[str, Any],
    sensitivity_data: dict[str, Any] | None = None,
    plot_data_uri: str | None = None,
    include_sensitivity: bool = True,
    n_sensitivity_sims: int = 300,
) -> str:
    """Generate a self-contained, reproducible HTML report from trial simulation results.

    Includes design assumptions, empirical power & dropout statistics, sensitivity plots,
    and a prominent research-prototype disclaimer.
    """
    scenario_dict = sim_result["scenario"]
    scenario = TrialScenario(**scenario_dict)
    op = sim_result["operating_characteristics"]
    assumptions = sim_result.get("assumptions_and_limitations", [])

    power = op["empirical_power"]
    mc_se = op["monte_carlo_se"]
    ci_lower = max(0.0, power - 1.96 * mc_se)
    ci_upper = min(1.0, power + 1.96 * mc_se)

    mean_effect = op.get("mean_effect_estimate")
    bias = op.get("bias")
    mean_ctrl = op["mean_n_control"]
    mean_trt = op["mean_n_treatment"]
    mean_retained_total = mean_ctrl + mean_trt
    planned_ctrl = scenario.n_per_arm
    planned_trt = math.ceil(scenario.n_per_arm * scenario.allocation_ratio)
    planned_total = planned_ctrl + planned_trt
    retention_pct = (mean_retained_total / planned_total) * 100 if planned_total > 0 else 0.0
    mean_effect_text = f"{mean_effect:.3f}" if mean_effect is not None else "N/A"
    bias_text = f"{bias:+.4f}" if bias is not None else "N/A"

    # Handle sensitivity if requested
    if include_sensitivity and sensitivity_data is None:
        sensitivity_data = run_sensitivity_grid(scenario, n_simulations=n_sensitivity_sims)

    if include_sensitivity and plot_data_uri is None and sensitivity_data is not None:
        plot_data_uri = generate_sensitivity_plots(sensitivity_data, scenario)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build sensitivity tables if data present
    sensitivity_html_rows = ""
    if sensitivity_data:
        eff_list = sensitivity_data.get("effect_sensitivity", [])
        drop_list = sensitivity_data.get("dropout_sensitivity", [])
        for i in range(max(len(eff_list), len(drop_list))):
            e_col = ""
            if i < len(eff_list):
                e = eff_list[i]
                e_col = f"<td>Δ = {e['effect']:.2f}</td><td><strong>{e['power']*100:.1f}%</strong> (±{e['se']*100:.1f}%)</td>"
            else:
                e_col = "<td>-</td><td>-</td>"

            d_col = ""
            if i < len(drop_list):
                d = drop_list[i]
                d_col = f"<td>{d['dropout_rate']*100:.0f}%</td><td><strong>{d['power']*100:.1f}%</strong> (±{d['se']*100:.1f}%)</td><td>{d['mean_retained_total']:.1f} pts</td>"
            else:
                d_col = "<td>-</td><td>-</td><td>-</td>"

            sensitivity_html_rows += f"<tr>{e_col}{d_col}</tr>\n"

    assumptions_li = "\n".join(f"<li>{escape(str(a))}</li>" for a in assumptions)
    scenario_name_html = escape(scenario.name)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clinical Trial Simulation Report - {scenario_name_html}</title>
  <style>
    :root {{
      --primary: #0284c7;
      --primary-dark: #0369a1;
      --slate-900: #0f172a;
      --slate-800: #1e293b;
      --slate-700: #334155;
      --slate-600: #475569;
      --slate-200: #e2e8f0;
      --slate-100: #f1f5f9;
      --slate-50: #f8fafc;
      --amber-50: #fffbeb;
      --amber-200: #fde68a;
      --amber-700: #b45309;
      --amber-900: #78350f;
      --emerald-600: #059669;
      --rose-600: #e11d48;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--slate-50);
      color: var(--slate-800);
      line-height: 1.55;
      padding: 2rem 1rem;
    }}
    .container {{
      max-width: 1080px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid var(--slate-200);
      border-radius: 12px;
      box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      color: #ffffff;
      padding: 2.2rem 2.5rem;
      border-bottom: 4px solid var(--primary);
    }}
    .header h1 {{
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-bottom: 0.3rem;
    }}
    .header .subtitle {{
      color: #94a3b8;
      font-size: 0.95rem;
      font-weight: 400;
    }}
    .meta-bar {{
      margin-top: 1.2rem;
      display: flex;
      flex-wrap: wrap;
      gap: 1.5rem;
      font-size: 0.82rem;
      color: #cbd5e1;
      padding-top: 0.8rem;
      border-top: 1px solid #334155;
    }}
    .meta-bar span strong {{ color: #ffffff; }}
    
    .disclaimer-banner {{
      background: var(--amber-50);
      border-left: 6px solid var(--amber-700);
      border-bottom: 1px solid var(--amber-200);
      padding: 1.2rem 1.8rem;
      color: var(--amber-900);
      font-size: 0.88rem;
    }}
    .disclaimer-banner h3 {{
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 0.35rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .disclaimer-banner p {{
      margin-bottom: 0.25rem;
      line-height: 1.45;
    }}

    .content {{
      padding: 2.2rem 2.5rem;
    }}

    .section-title {{
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--slate-900);
      margin-top: 2rem;
      margin-bottom: 1rem;
      padding-bottom: 0.4rem;
      border-bottom: 2px solid var(--slate-100);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .section-title:first-of-type {{ margin-top: 0; }}

    /* KPI Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.2rem;
      margin-bottom: 1.8rem;
    }}
    .kpi-card {{
      background: var(--slate-50);
      border: 1px solid var(--slate-200);
      border-radius: 8px;
      padding: 1.2rem 1.4rem;
    }}
    .kpi-label {{
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--slate-600);
      font-weight: 600;
      margin-bottom: 0.4rem;
    }}
    .kpi-value {{
      font-size: 1.7rem;
      font-weight: 700;
      color: var(--slate-900);
      line-height: 1.1;
    }}
    .kpi-subtext {{
      font-size: 0.8rem;
      color: var(--slate-600);
      margin-top: 0.35rem;
    }}

    /* Tables */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
      margin-top: 0.6rem;
      margin-bottom: 1.4rem;
    }}
    th, td {{
      padding: 0.75rem 0.9rem;
      text-align: left;
      border-bottom: 1px solid var(--slate-200);
    }}
    th {{
      background: var(--slate-100);
      color: var(--slate-700);
      font-weight: 600;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    tr:hover td {{
      background: #f8fafc;
    }}

    .badge {{
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }}
    .badge-primary {{ background: #e0f2fe; color: #0369a1; }}
    .badge-success {{ background: #dcfce7; color: #15803d; }}
    .badge-warning {{ background: #fef3c7; color: #b45309; }}

    .plot-container {{
      background: #ffffff;
      border: 1px solid var(--slate-200);
      border-radius: 8px;
      padding: 1rem;
      text-align: center;
      margin-top: 0.8rem;
      margin-bottom: 1.5rem;
    }}
    .plot-container img {{
      max-width: 100%;
      height: auto;
      border-radius: 4px;
    }}

    .callout {{
      background: #f0fdf4;
      border-left: 4px solid var(--emerald-600);
      padding: 1rem 1.2rem;
      font-size: 0.85rem;
      margin: 1.2rem 0;
      border-radius: 0 6px 6px 0;
    }}
    .callout-info {{
      background: #f0f9ff;
      border-left: 4px solid var(--primary);
    }}

    ul.assumptions-list {{
      padding-left: 1.4rem;
      font-size: 0.88rem;
      color: var(--slate-700);
      margin-bottom: 1.5rem;
    }}
    ul.assumptions-list li {{
      margin-bottom: 0.4rem;
    }}

    .footer {{
      background: var(--slate-100);
      border-top: 1px solid var(--slate-200);
      padding: 1.5rem 2.5rem;
      font-size: 0.82rem;
      color: var(--slate-600);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
    }}
  </style>
</head>
<body>

<div class="container">
  <!-- Header -->
  <div class="header">
    <h1>Clinical Trial Simulation Report</h1>
    <div class="subtitle">Scenario: <strong>{scenario_name_html}</strong> • Synthetic Monte Carlo Operating Characteristics</div>
    <div class="meta-bar">
      <span>Timestamp: <strong>{now_utc}</strong></span>
      <span>Simulations: <strong>{scenario.n_simulations:,}</strong></span>
      <span>RNG Seed: <strong>{scenario.seed}</strong></span>
      <span>Software: <strong>clinical-trial-simulation-agent v0.1.0</strong></span>
    </div>
  </div>

  <!-- Mandatory Research-Prototype Disclaimer -->
  <div class="disclaimer-banner">
    <h3>⚠ Methodological Exploration Only — Not for Clinical or Regulatory Decisions</h3>
    <p>
      This simulation report was generated by an open-source research and teaching prototype. It is <strong>NOT</strong> validated software for clinical trials, regulatory filings (FDA/EMA/ICH), or healthcare decisions. All patient distributions, dropout probabilities, and site shifts are synthetic.
    </p>
    <p>
      Formal trial sizing for investigational protocols requires an approved Statistical Analysis Plan (SAP), validated statistical computing environments (e.g., compliant SAS/R), pre-specified estimands per ICH E9(R1), and multi-site observational calibration.
    </p>
  </div>

  <div class="content">
    <!-- Key Operating Characteristics (KPI Cards) -->
    <div class="section-title">1. Operating Characteristics Summary</div>
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Empirical Power</div>
        <div class="kpi-value" style="color: {'#059669' if power >= 0.80 else '#b45309'};">{power * 100:.1f}%</div>
        <div class="kpi-subtext">MC-SE: ±{mc_se * 100:.2f}% • approx. 95% MC interval: [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Treatment Effect (Mean Estimate)</div>
        <div class="kpi-value">{mean_effect_text}</div>
        <div class="kpi-subtext">True Effect Δ = {scenario.true_effect:.3f} • Bias: {bias_text}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Planned Enrollment</div>
        <div class="kpi-value">{planned_total} pts</div>
        <div class="kpi-subtext">{planned_ctrl} Control : {planned_trt} Treatment (Ratio {scenario.allocation_ratio}:1)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Retained Sample Size</div>
        <div class="kpi-value">{mean_retained_total:.1f} pts</div>
        <div class="kpi-subtext">{retention_pct:.1f}% retention (Dropout: {scenario.dropout_rate*100:.0f}%, {scenario.missingness_mechanism})</div>
      </div>
    </div>

    <!-- Power & Dropout Detailed Comparison -->
    <div class="section-title">2. Sample Size, Retention, and Dropout Operating Characteristics</div>
    <table>
      <thead>
        <tr>
          <th>Trial Arm</th>
          <th>Planned N</th>
          <th>Dropout Rate Assumption</th>
          <th>Mean Retained N</th>
          <th>Mean Retention Rate</th>
          <th>Missingness Model</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Control Arm</strong></td>
          <td>{planned_ctrl}</td>
          <td>{scenario.dropout_rate*100:.1f}%</td>
          <td>{mean_ctrl:.1f}</td>
          <td>{(mean_ctrl / planned_ctrl * 100) if planned_ctrl else 0:.1f}%</td>
          <td>{scenario.missingness_mechanism}</td>
        </tr>
        <tr>
          <td><strong>Treatment Arm</strong></td>
          <td>{planned_trt}</td>
          <td>{scenario.dropout_rate*100:.1f}%</td>
          <td>{mean_trt:.1f}</td>
          <td>{(mean_trt / planned_trt * 100) if planned_trt else 0:.1f}%</td>
          <td>{scenario.missingness_mechanism}</td>
        </tr>
        <tr style="background: var(--slate-100); font-weight: 600;">
          <td>Total Trial Cohort</td>
          <td>{planned_total}</td>
          <td>{scenario.dropout_rate*100:.1f}% overall</td>
          <td>{mean_retained_total:.1f}</td>
          <td>{retention_pct:.1f}%</td>
          <td>{scenario.missingness_mechanism}</td>
        </tr>
      </tbody>
    </table>

    <!-- Design Assumptions Table -->
    <div class="section-title">3. Design Assumptions and Parametric Setup</div>
    <table>
      <thead>
        <tr>
          <th>Parameter</th>
          <th>Assumed Value</th>
          <th>Category</th>
          <th>Methodological Note</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Significance Level (α)</strong></td>
          <td>{scenario.alpha} (two-sided)</td>
          <td><span class="badge badge-primary">Statistical</span></td>
          <td>Standard type I error threshold; Welch's unequal variance t-test</td>
        </tr>
        <tr>
          <td><strong>True Treatment Effect (Δ)</strong></td>
          <td>{scenario.true_effect}</td>
          <td><span class="badge badge-primary">Efficacy Prior</span></td>
          <td>True underlying additive shift between treatment and control means</td>
        </tr>
        <tr>
          <td><strong>Endpoint Standard Deviation (σ)</strong></td>
          <td>{scenario.endpoint_sd}</td>
          <td><span class="badge badge-primary">Variance Prior</span></td>
          <td>Cohen's d = {scenario.true_effect / scenario.endpoint_sd:.3f}</td>
        </tr>
        <tr>
          <td><strong>Sample Size Allocation</strong></td>
          <td>{scenario.n_per_arm} per arm (Ratio {scenario.allocation_ratio}:1)</td>
          <td><span class="badge badge-primary">Sample Size</span></td>
          <td>Planned enrollment across arms prior to dropouts</td>
        </tr>
        <tr>
          <td><strong>Anticipated Patient Dropout Rate</strong></td>
          <td>{scenario.dropout_rate * 100:.1f}%</td>
          <td><span class="badge badge-warning">Operational Risk</span></td>
          <td>Binomial retention process per patient arm</td>
        </tr>
        <tr>
          <td><strong>Non-Adherence Rate</strong></td>
          <td>{scenario.nonadherence_rate * 100:.1f}%</td>
          <td><span class="badge badge-warning">Operational Risk</span></td>
          <td>Simulates intention-to-treat (ITT) treatment effect attenuation</td>
        </tr>
        <tr>
          <td><strong>Site Heterogeneity SD</strong></td>
          <td>{scenario.site_heterogeneity_sd:.2f}</td>
          <td><span class="badge badge-warning">Site Operations</span></td>
          <td>Between-site additive random variation in baseline response</td>
        </tr>
        <tr>
          <td><strong>Recruitment Duration</strong></td>
          <td>{scenario.recruitment_months} months</td>
          <td><span class="badge badge-warning">Timeline</span></td>
          <td>Target operational enrollment window</td>
        </tr>
        <tr>
          <td><strong>Missing Data Representation</strong></td>
          <td>{scenario.missingness_mechanism}</td>
          <td><span class="badge badge-warning">Missing Data</span></td>
          <td>Simplified sensitivity proxy for stress-testing protocol robustness</td>
        </tr>
      </tbody>
    </table>

    <!-- Sensitivity Plots Section -->
    <div class="section-title">4. Sensitivity Analysis & Robustness Curves</div>
    <p style="font-size: 0.88rem; color: var(--slate-600); margin-bottom: 0.8rem;">
      Empirical power evaluated across three key dimensions: treatment effect perturbation, sample size scaling, and elevated patient dropout.
    </p>

    {"<div class='plot-container'><img src='" + plot_data_uri + "' alt='Clinical Trial Simulation Sensitivity Curves' /></div>" if plot_data_uri else "<p><em>No sensitivity plot generated.</em></p>"}

    {"<table><thead><tr><th>Perturbed Effect (Δ)</th><th>Simulated Power</th><th>Dropout Rate</th><th>Power Impact</th><th>Retained N</th></tr></thead><tbody>" + sensitivity_html_rows + "</tbody></table>" if sensitivity_html_rows else ""}

    <!-- Stated Assumptions and Protocol Governance -->
    <div class="section-title">5. Stated Model Assumptions & Limitations</div>
    <ul class="assumptions-list">
      {assumptions_li}
    </ul>

    <div class="callout callout-info">
      <strong>Regulatory Context (ICH E9 / FDA Guidance on Complex Innovative Trial Designs):</strong>
      Modern clinical trial simulation (CTS) plays a vital role in assessing operating characteristics (e.g. power, type I error inflation, and missing data impacts) before finalizing phase II/III protocols. However, regulatory acceptance requires formal model validation, sensitivity audits for non-ignorable dropouts (MNAR pattern-mixture or tipping-point analyses), and complete transparency in random seed management.
    </div>

  </div>

  <!-- Footer -->
  <div class="footer">
    <span>Clinical Trial Simulation Agent • Reproducible Research Pipeline</span>
    <span>MIT License • <a href="https://github.com/gyagu98/clinical-trial-simulation-agent" style="color: var(--primary);">GitHub Repository</a></span>
  </div>
</div>

</body>
</html>
"""
    return html
