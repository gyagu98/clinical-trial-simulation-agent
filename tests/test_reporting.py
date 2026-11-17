"""Tests for HTML report generation and sensitivity visualizations."""
import json
import subprocess
import sys
from pathlib import Path

from trial_sim.reporting.html_report import generate_html_report
from trial_sim.reporting.sensitivity import (
    generate_sensitivity_plots,
    run_sensitivity_grid,
)
from trial_sim.simulation.engine import simulate_trial
from trial_sim.simulation.scenarios import TrialScenario


def test_run_sensitivity_grid():
    sc = TrialScenario(
        name="test_grid",
        n_per_arm=40,
        true_effect=0.4,
        endpoint_sd=1.0,
        dropout_rate=0.1,
        n_simulations=50,
        seed=123,
    )
    grid = run_sensitivity_grid(
        sc,
        effect_sizes=[0.0, 0.4, 0.8],
        sample_sizes=[20, 40, 80],
        dropout_rates=[0.0, 0.15, 0.30],
        n_simulations=50,
    )

    assert "effect_sensitivity" in grid
    assert "sample_size_sensitivity" in grid
    assert "dropout_sensitivity" in grid

    # Power for large effect should exceed null
    eff = grid["effect_sensitivity"]
    assert eff[-1]["power"] >= eff[0]["power"]
    assert 0.0 <= eff[0]["power"] <= 1.0


def test_generate_sensitivity_plots():
    sc = TrialScenario(
        name="test_plot",
        n_per_arm=30,
        true_effect=0.3,
        endpoint_sd=1.0,
        dropout_rate=0.05,
        n_simulations=30,
        seed=42,
    )
    grid = run_sensitivity_grid(
        sc,
        effect_sizes=[0.0, 0.3, 0.6],
        sample_sizes=[20, 30],
        dropout_rates=[0.0, 0.1],
        n_simulations=30,
    )
    uri = generate_sensitivity_plots(grid, sc)

    assert isinstance(uri, str)
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 1000


def test_generate_html_report_contains_required_sections():
    sc = TrialScenario(
        name="Phase2_Demo",
        n_per_arm=50,
        true_effect=0.35,
        endpoint_sd=1.0,
        dropout_rate=0.12,
        n_simulations=60,
        seed=99,
    )
    result = simulate_trial(sc)
    html = generate_html_report(result, include_sensitivity=True, n_sensitivity_sims=30)

    assert "<!DOCTYPE html>" in html
    assert "Phase2_Demo" in html
    # Research prototype disclaimer check
    assert "Methodological Exploration Only" in html
    assert "Not for Clinical or Regulatory Decisions" in html
    # Operating characteristics and dropout summaries check
    assert "Operating Characteristics Summary" in html
    assert "Empirical Power" in html
    assert "Retained Sample Size" in html
    assert "Design Assumptions" in html
    assert "Sensitivity Analysis" in html
    # Embedded plot check
    assert "data:image/png;base64," in html


def test_generate_html_report_without_sensitivity():
    sc = TrialScenario(
        name="Fast_Report",
        n_per_arm=30,
        true_effect=0.25,
        endpoint_sd=1.0,
        dropout_rate=0.08,
        n_simulations=40,
        seed=101,
    )
    result = simulate_trial(sc)
    html = generate_html_report(result, include_sensitivity=False)

    assert "Fast_Report" in html
    assert "Methodological Exploration Only" in html
    assert "Empirical Power" in html


def test_cli_simulate_with_report(tmp_path: Path):
    out_json = tmp_path / "sim.json"
    out_html = tmp_path / "report.html"

    cmd = [
        sys.executable,
        "-m",
        "trial_sim.cli",
        "simulate",
        "--name",
        "CLI_Test",
        "--n-per-arm",
        "30",
        "--effect",
        "0.3",
        "--dropout",
        "0.1",
        "--n-simulations",
        "40",
        "--out",
        str(out_json),
        "--report",
        str(out_html),
        "--no-sensitivity",
    ]
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert res.returncode == 0, f"CLI simulate failed: {res.stderr}"

    assert out_json.exists()
    assert out_html.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert "operating_characteristics" in data
    html = out_html.read_text(encoding="utf-8")
    assert "CLI_Test" in html
    assert "Methodological Exploration Only" in html


def test_cli_report_subcommand(tmp_path: Path):
    out_json = tmp_path / "sim_existing.json"
    out_html = tmp_path / "report_from_json.html"

    sc = TrialScenario(
        name="Existing_Run",
        n_per_arm=40,
        true_effect=0.3,
        endpoint_sd=1.0,
        dropout_rate=0.1,
        n_simulations=40,
        seed=777,
    )
    result = simulate_trial(sc)
    out_json.write_text(json.dumps(result), encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "trial_sim.cli",
        "report",
        "--result",
        str(out_json),
        "--out",
        str(out_html),
        "--no-sensitivity",
    ]
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert res.returncode == 0, f"CLI report failed: {res.stderr}"

    assert out_html.exists()
    html = out_html.read_text(encoding="utf-8")
    assert "Existing_Run" in html
    assert "Empirical Power" in html
