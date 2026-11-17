"""Sensitivity analysis and visualization for clinical trial simulation scenarios."""
from __future__ import annotations

import base64
import io
from dataclasses import replace
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..simulation.engine import simulate_trial
from ..simulation.scenarios import TrialScenario


def run_sensitivity_grid(
    base_scenario: TrialScenario,
    effect_sizes: list[float] | None = None,
    sample_sizes: list[int] | None = None,
    dropout_rates: list[float] | None = None,
    n_simulations: int = 300,
) -> dict[str, Any]:
    """Evaluate power operating characteristics across perturbations of key assumptions.

    Parameters are evaluated while holding other parameters fixed at base_scenario values.
    """
    if effect_sizes is None:
        delta = max(0.1, abs(base_scenario.true_effect))
        effect_sizes = [
            round(x, 2)
            for x in [0.0, delta * 0.5, delta * 0.75, delta, delta * 1.25, delta * 1.5]
        ]
    if sample_sizes is None:
        base_n = base_scenario.n_per_arm
        sample_sizes = sorted(
            {
                max(10, int(base_n * 0.5)),
                max(15, int(base_n * 0.75)),
                base_n,
                int(base_n * 1.25),
                int(base_n * 1.5),
                int(base_n * 2.0),
            }
        )
    if dropout_rates is None:
        dropout_rates = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

    # 1. Effect size sensitivity
    effect_results = []
    for eff in effect_sizes:
        sc = replace(base_scenario, true_effect=eff, n_simulations=n_simulations)
        sim = simulate_trial(sc)
        p = sim["operating_characteristics"]["empirical_power"]
        se = sim["operating_characteristics"]["monte_carlo_se"]
        effect_results.append({"effect": eff, "power": p, "se": se})

    # 2. Sample size sensitivity
    sample_results = []
    for n in sample_sizes:
        sc = replace(base_scenario, n_per_arm=n, n_simulations=n_simulations)
        sim = simulate_trial(sc)
        p = sim["operating_characteristics"]["empirical_power"]
        se = sim["operating_characteristics"]["monte_carlo_se"]
        sample_results.append({"n_per_arm": n, "power": p, "se": se})

    # 3. Dropout sensitivity
    dropout_results = []
    for dr in dropout_rates:
        sc = replace(base_scenario, dropout_rate=dr, n_simulations=n_simulations)
        sim = simulate_trial(sc)
        p = sim["operating_characteristics"]["empirical_power"]
        se = sim["operating_characteristics"]["monte_carlo_se"]
        mean_n_ctrl = sim["operating_characteristics"]["mean_n_control"]
        mean_n_trt = sim["operating_characteristics"]["mean_n_treatment"]
        dropout_results.append({
            "dropout_rate": dr,
            "power": p,
            "se": se,
            "mean_retained_total": mean_n_ctrl + mean_n_trt,
        })

    return {
        "base_scenario": base_scenario.name,
        "n_simulations_per_point": n_simulations,
        "effect_sensitivity": effect_results,
        "sample_size_sensitivity": sample_results,
        "dropout_sensitivity": dropout_results,
    }


def generate_sensitivity_plots(
    sensitivity_data: dict[str, Any],
    base_scenario: TrialScenario,
) -> str:
    """Generate a multi-panel sensitivity figure and return it as a base64 PNG data URI."""
    eff_data = sensitivity_data.get("effect_sensitivity", [])
    n_data = sensitivity_data.get("sample_size_sensitivity", [])
    drop_data = sensitivity_data.get("dropout_sensitivity", [])
    y_drop: list[float] = []

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), dpi=130)
    plt.subplots_adjust(wspace=0.32, bottom=0.18, top=0.88)

    for ax in axes:
        ax.set_facecolor("#fcfdfe")
        ax.grid(True, linestyle="--", alpha=0.5, color="#cbd5e1")
        ax.axhline(0.80, color="#dc2626", linestyle=":", linewidth=1.2, label="80% Power Threshold")
        ax.axhline(0.90, color="#2563eb", linestyle=":", linewidth=1.2, label="90% Power Threshold")
        ax.set_ylim(-0.02, 1.05)
        ax.set_ylabel("Empirical Power", fontsize=10, fontweight="medium", color="#1e293b")

    # Panel 1: Power vs. True Effect Size
    if eff_data:
        x_eff = [d["effect"] for d in eff_data]
        y_eff = [d["power"] for d in eff_data]
        err_eff = [d["se"] * 1.96 for d in eff_data]
        axes[0].errorbar(
            x_eff, y_eff, yerr=err_eff, fmt="-o", color="#0284c7", ecolor="#93c5fd",
            capsize=3, linewidth=2, markersize=5, label="Simulated Power (95% CI)",
        )
        base_eff = base_scenario.true_effect
        axes[0].axvline(base_eff, color="#0f766e", linestyle="--", alpha=0.7, label=f"Base ({base_eff})")
        axes[0].set_xlabel("True Treatment Effect (Δ)", fontsize=10, fontweight="medium", color="#1e293b")
        axes[0].set_title("A: Sensitivity to Effect Size", fontsize=11, fontweight="bold", color="#0f172a")

    # Panel 2: Power vs. Sample Size per Arm
    if n_data:
        x_n = [d["n_per_arm"] for d in n_data]
        y_n = [d["power"] for d in n_data]
        err_n = [d["se"] * 1.96 for d in n_data]
        axes[1].errorbar(
            x_n, y_n, yerr=err_n, fmt="-s", color="#7c3aed", ecolor="#c4b5fd",
            capsize=3, linewidth=2, markersize=5, label="Simulated Power (95% CI)",
        )
        base_n = base_scenario.n_per_arm
        axes[1].axvline(base_n, color="#0f766e", linestyle="--", alpha=0.7, label=f"Base N ({base_n})")
        axes[1].set_xlabel("Sample Size per Arm (N)", fontsize=10, fontweight="medium", color="#1e293b")
        axes[1].set_title("B: Sensitivity to Sample Size", fontsize=11, fontweight="bold", color="#0f172a")

    # Panel 3: Power vs. Dropout Rate
    if drop_data:
        x_drop = [d["dropout_rate"] * 100 for d in drop_data]
        y_drop = [d["power"] for d in drop_data]
        err_drop = [d["se"] * 1.96 for d in drop_data]
        axes[2].errorbar(
            x_drop, y_drop, yerr=err_drop, fmt="-^", color="#d97706", ecolor="#fde68a",
            capsize=3, linewidth=2, markersize=5, label="Simulated Power (95% CI)",
        )
        base_dr = base_scenario.dropout_rate * 100
        axes[2].axvline(base_dr, color="#0f766e", linestyle="--", alpha=0.7, label=f"Base ({base_dr:.0f}%)")
        axes[2].set_xlabel("Anticipated Dropout Rate (%)", fontsize=10, fontweight="medium", color="#1e293b")
        axes[2].set_title("C: Power Impact of Patient Dropout", fontsize=11, fontweight="bold", color="#0f172a")

    axes[0].legend(loc="lower right", fontsize=8, framealpha=0.9)
    axes[1].legend(loc="lower right", fontsize=8, framealpha=0.9)
    axes[2].legend(loc="lower left" if y_drop and y_drop[-1] < 0.5 else "upper right", fontsize=8, framealpha=0.9)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
