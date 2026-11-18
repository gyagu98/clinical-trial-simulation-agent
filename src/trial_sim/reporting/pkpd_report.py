"""Self-contained HTML report generator for Population PK/PD simulations."""

from __future__ import annotations

import base64
import html
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from trial_sim.simulation.pkpd import PopulationPKPDResult


def _render_plots_to_base64_png(result: PopulationPKPDResult) -> str:
    """Render dual-panel PK and PD curves to a single high-DPI base64 PNG image."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, dpi=130)
    
    t = np.array(result.time_grid)
    med_conc = np.array(result.median_conc)
    p05_conc = np.array(result.p05_conc)
    p95_conc = np.array(result.p95_conc)
    
    med_te = np.array(result.median_target_engagement)
    p05_te = np.array(result.p05_target_engagement)
    p95_te = np.array(result.p95_target_engagement)
    
    # 1. PK Concentration Panel
    ax1.fill_between(t, p05_conc, p95_conc, color='#0284c7', alpha=0.22, label='90% Population Interval (P05-P95)')
    ax1.plot(t, med_conc, color='#0369a1', linewidth=2.4, label='Median Plasma Concentration')
    
    # Overlay a few individual profiles
    for i, prof in enumerate(result.individual_profiles[:5]):
        ax1.plot(prof.time_hours, prof.conc_central_mg_l, color='#64748b', linewidth=0.8, alpha=0.45,
                 label='Individual Subjects (IIV)' if i == 0 else "")
        
    ax1.set_ylabel('Central Conc. (mg/L)', fontsize=11, fontweight='bold', color='#1e293b')
    ax1.set_title('Two-Compartment Population Pharmacokinetics (IIV on CL, Vc, ka)', fontsize=12, fontweight='bold', pad=10)
    ax1.grid(True, linestyle='--', alpha=0.45, color='#cbd5e1')
    ax1.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)
    ax1.set_xlim(0, t[-1])
    ax1.set_ylim(bottom=0)
    
    # 2. PD Target Engagement Panel
    ax2.fill_between(t, p05_te, p95_te, color='#16a34a', alpha=0.20, label='90% Population Interval (P05-P95)')
    ax2.plot(t, med_te, color='#15803d', linewidth=2.4, label='Median Target Engagement (%)')
    
    # Reference target threshold (90% target engagement)
    ax2.axhline(90.0, color='#dc2626', linestyle=':', linewidth=1.5, label='Target Threshold (90% TE)')
    
    for i, prof in enumerate(result.individual_profiles[:5]):
        ax2.plot(prof.time_hours, prof.target_engagement_pct, color='#64748b', linewidth=0.8, alpha=0.45)
        
    ax2.set_xlabel('Time (hours)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.set_ylabel('Target Engagement (%)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.set_title('Pharmacodynamic Response (Sigmoidal Emax / Hill Model)', fontsize=12, fontweight='bold', pad=10)
    ax2.set_ylim(0, 105)
    ax2.grid(True, linestyle='--', alpha=0.45, color='#cbd5e1')
    ax2.legend(loc='lower right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)
    
    plt.tight_layout()
    
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('ascii')


def generate_pkpd_html_report(result: PopulationPKPDResult, title: str = "Population PK/PD Simulation Report") -> str:
    """Produce self-contained HTML report with embedded visuals and exposure metrics."""
    plot_b64 = _render_plots_to_base64_png(result)
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    pk = result.parameters_pk
    pd = result.parameters_pd
    reg = result.regimen
    m = result.metrics
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        :root {{
            --primary: #0284c7;
            --primary-dark: #0369a1;
            --secondary: #16a34a;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            line-height: 1.5;
            margin: 0;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 1040px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #0369a1, #0f172a);
            color: white;
            padding: 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 26px;
            letter-spacing: -0.02em;
        }}
        .header p {{
            margin: 0;
            color: #bae6fd;
            font-size: 14px;
        }}
        .badge {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.15);
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
        }}
        .disclaimer-card {{
            background: #fffbeb;
            border-left: 4px solid #f59e0b;
            padding: 16px 20px;
            border-radius: 6px;
            margin-bottom: 24px;
            font-size: 13px;
            color: #92400e;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .card-title {{
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}
        .card-value {{
            font-size: 24px;
            font-weight: 800;
            color: var(--text-main);
        }}
        .card-subtext {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .plot-container {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .plot-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 6px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 10px;
        }}
        th, td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background-color: #f1f5f9;
            color: #475569;
            font-weight: 600;
        }}
        tr:hover td {{
            background-color: #f8fafc;
        }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{html.escape(title)}</h1>
            <p>Two-Compartment Pharmacometrics & Population PK/PD Simulation Engine</p>
            <div class="badge">N = {result.n_subjects} Simulated Subjects &bull; {reg['route'].upper()} Dosing &bull; tau = {reg['interval_hours']}h</div>
        </div>

        <div class="disclaimer-card">
            <strong>Research & Education Prototype:</strong> This simulation is intended for in silico trial design, pharmacometric scenario planning, and methodology evaluation. Parameters are derived from mathematical compartments and should not be used for direct clinical dosing or regulatory drug submissions without clinical bioequivalence validation.
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-title">Steady-State Cmax</div>
                <div class="card-value">{m['cmax_ss']['median']:.2f} <span style="font-size:14px;font-weight:normal;color:#64748b">mg/L</span></div>
                <div class="card-subtext">Mean: {m['cmax_ss']['mean']:.2f} ± {m['cmax_ss']['std']:.2f} (CV: {m['cmax_ss']['cv_pct']:.1f}%)</div>
            </div>
            <div class="card">
                <div class="card-title">Steady-State Ctrough</div>
                <div class="card-value">{m['ctrough_ss']['median']:.2f} <span style="font-size:14px;font-weight:normal;color:#64748b">mg/L</span></div>
                <div class="card-subtext">Mean: {m['ctrough_ss']['mean']:.2f} ± {m['ctrough_ss']['std']:.2f} (CV: {m['ctrough_ss']['cv_pct']:.1f}%)</div>
            </div>
            <div class="card">
                <div class="card-title">AUC (0-tau)</div>
                <div class="card-value">{m['auc_tau']['median']:.1f} <span style="font-size:14px;font-weight:normal;color:#64748b">mg·h/L</span></div>
                <div class="card-subtext">IQR: [{m['auc_tau']['p25']:.1f} - {m['auc_tau']['p75']:.1f}] mg·h/L</div>
            </div>
            <div class="card">
                <div class="card-title">Time Above EC90</div>
                <div class="card-value" style="color: {('#16a34a' if m['time_above_ec90_pct']['median'] >= 75.0 else '#d97706')};">{m['time_above_ec90_pct']['median']:.1f}%</div>
                <div class="card-subtext">Target Coverage at Steady-State</div>
            </div>
        </div>

        <div class="plot-container">
            <h3 style="margin-top:0; color:#1e293b; text-align:left;">Population Exposure-Response Curves</h3>
            <img src="data:image/png;base64,{plot_b64}" alt="PK/PD Population Profile">
        </div>

        <div class="card" style="margin-bottom:24px;">
            <h3 style="margin-top:0; color:#1e293b;">Pharmacometric Structural Parameters</h3>
            <table>
                <thead>
                    <tr>
                        <th>Parameter</th>
                        <th>Symbol</th>
                        <th>Population Typical Value</th>
                        <th>IIV (CV%)</th>
                        <th>Biological Significance</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Clearance</strong></td>
                        <td>CL</td>
                        <td>{pk['cl']:.1f} L/h</td>
                        <td>{pk['omega_cl']*100:.0f}%</td>
                        <td>Hepatic / renal elimination capacity</td>
                    </tr>
                    <tr>
                        <td><strong>Central Volume</strong></td>
                        <td>Vc</td>
                        <td>{pk['vc']:.1f} L</td>
                        <td>{pk['omega_vc']*100:.0f}%</td>
                        <td>Vascular / well-perfused tissue distribution</td>
                    </tr>
                    <tr>
                        <td><strong>Intercompartmental Clearance</strong></td>
                        <td>Q</td>
                        <td>{pk['q']:.1f} L/h</td>
                        <td>-</td>
                        <td>Permeability between central and peripheral pools</td>
                    </tr>
                    <tr>
                        <td><strong>Peripheral Volume</strong></td>
                        <td>Vp</td>
                        <td>{pk['vp']:.1f} L</td>
                        <td>-</td>
                        <td>Deep tissue storage and accumulation pool</td>
                    </tr>
                    <tr>
                        <td><strong>Absorption Rate</strong></td>
                        <td>ka</td>
                        <td>{pk['ka']:.2f} 1/h</td>
                        <td>{pk['omega_ka']*100:.0f}%</td>
                        <td>GI tract drug absorption velocity</td>
                    </tr>
                    <tr>
                        <td><strong>Potency (EC50 / IC50)</strong></td>
                        <td>EC50</td>
                        <td>{pd['ec50']:.2f} mg/L</td>
                        <td>-</td>
                        <td>Drug concentration for half-maximal target engagement</td>
                    </tr>
                    <tr>
                        <td><strong>Hill Coefficient</strong></td>
                        <td>&gamma;</td>
                        <td>{pd['gamma']:.2f}</td>
                        <td>-</td>
                        <td>Sigmoidal cooperativity of receptor binding</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="footer">
            Generated with <strong>clinical-trial-simulation-agent</strong> (v0.2.0) &bull; {generated_at}
        </div>
    </div>
</body>
</html>
"""
    return html_content
