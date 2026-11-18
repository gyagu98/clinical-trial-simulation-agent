"""Unit tests for two-compartment population PK/PD simulation engine and reporting."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from trial_sim.reporting.pkpd_report import generate_pkpd_html_report
from trial_sim.simulation.pkpd import (
    DosingRegimen,
    PDParameters,
    PKParameters,
    _micro_rate_constants,
    simulate_population_pkpd,
    simulate_subject_pkpd,
)


def test_micro_rate_constants():
    k10, k12, k21, alpha, beta = _micro_rate_constants(cl=5.0, vc=20.0, q=8.0, vp=40.0)
    assert k10 == pytest.approx(0.25)
    assert k12 == pytest.approx(0.40)
    assert k21 == pytest.approx(0.20)
    assert alpha > beta
    assert alpha * beta == pytest.approx(k10 * k21)
    assert (alpha + beta) == pytest.approx(k10 + k12 + k21)


def test_single_subject_oral_pk():
    pk = PKParameters(cl=5.0, vc=20.0, q=5.0, vp=30.0, ka=1.5, bioavailability=0.8)
    pd = PDParameters(emax=90.0, ec50=1.0)
    regimen = DosingRegimen(dose_mg=100.0, route="oral", interval_hours=24.0, num_doses=1)
    
    times = np.linspace(0, 48, 193)
    prof = simulate_subject_pkpd(
        subject_id=1,
        cl=pk.cl,
        vc=pk.vc,
        q=pk.q,
        vp=pk.vp,
        ka=pk.ka,
        bioavailability=pk.bioavailability,
        pd_params=pd,
        regimen=regimen,
        time_points=times,
    )
    
    assert prof.conc_central_mg_l[0] == pytest.approx(0.0)
    assert prof.cmax_ss > 0.5
    assert prof.tmax_ss > 0.0
    assert prof.auc_tau > 0.0
    # Concentration at t=48 should be much lower than Cmax
    assert prof.conc_central_mg_l[-1] < prof.cmax_ss * 0.1


def test_multi_dose_accumulation():
    pk = PKParameters(cl=3.0, vc=25.0, q=6.0, vp=50.0, ka=1.0)
    pd = PDParameters(emax=95.0, ec50=2.0)
    
    # Single dose
    reg_single = DosingRegimen(dose_mg=100.0, route="oral", interval_hours=24.0, num_doses=1)
    prof_single = simulate_subject_pkpd(1, pk.cl, pk.vc, pk.q, pk.vp, pk.ka, pk.bioavailability, pd, reg_single, np.linspace(0, 24, 97))
    
    # 7 repeated daily doses
    reg_multi = DosingRegimen(dose_mg=100.0, route="oral", interval_hours=24.0, num_doses=7)
    prof_multi = simulate_subject_pkpd(1, pk.cl, pk.vc, pk.q, pk.vp, pk.ka, pk.bioavailability, pd, reg_multi, np.linspace(0, 168, 673))
    
    # Steady-state Cmax should show accumulation (>= single dose Cmax)
    assert prof_multi.cmax_ss >= prof_single.cmax_ss
    assert prof_multi.ctrough_ss > 0.0


def test_population_simulation_iiv():
    pk = PKParameters(cl=5.0, vc=20.0, omega_cl=0.30, omega_vc=0.25)
    pd = PDParameters()
    reg = DosingRegimen(num_doses=5, interval_hours=24.0)
    
    res = simulate_population_pkpd(pk_params=pk, pd_params=pd, regimen=reg, n_subjects=50, seed=123)
    
    assert res.n_subjects == 50
    assert len(res.median_conc) == len(res.time_grid)
    # Check that 95th percentile >= median >= 5th percentile
    assert np.all(np.array(res.p95_conc) >= np.array(res.median_conc))
    assert np.all(np.array(res.median_conc) >= np.array(res.p05_conc))
    
    # Check metric statistics
    assert res.metrics["cmax_ss"]["mean"] > 0.0
    assert res.metrics["auc_tau"]["median"] > 0.0
    assert 0.0 <= res.metrics["time_above_ec90_pct"]["median"] <= 100.0


def test_pkpd_html_report_generation(tmp_path):
    res = simulate_population_pkpd(n_subjects=20, seed=42)
    html_out = generate_pkpd_html_report(res, title="Test PK/PD Report")
    
    assert "<!DOCTYPE html>" in html_out
    assert "Test PK/PD Report" in html_out
    assert "data:image/png;base64," in html_out
    assert "Pharmacometric Structural Parameters" in html_out
    assert "Research & Education Prototype" in html_out
    
    report_file = tmp_path / "pkpd_report.html"
    report_file.write_text(html_out, encoding="utf-8")
    assert report_file.exists()
    assert report_file.stat().st_size > 10000


def test_cli_simulate_pkpd(tmp_path):
    json_path = tmp_path / "pkpd_res.json"
    html_path = tmp_path / "pkpd_report.html"
    
    cmd = [
        sys.executable,
        "-m",
        "trial_sim",
        "simulate-pkpd",
        "--dose", "150.0",
        "--n-subjects", "25",
        "--out", str(json_path),
        "--report", str(html_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    
    assert json_path.exists()
    assert html_path.exists()
    
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["n_subjects"] == 25
    assert "steady_state_summary" in data
    assert data["steady_state_summary"]["median_cmax_mg_l"] > 0.0
