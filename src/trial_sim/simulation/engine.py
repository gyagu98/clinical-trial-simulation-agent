"""Monte Carlo operating-characteristic engine for a two-arm continuous endpoint."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
from scipy import stats

from .scenarios import TrialScenario


def _simulate_once(scenario: TrialScenario, rng: np.random.Generator) -> dict[str, Any]:
    """Simulate a single trial under the configured simple design assumptions."""
    # Enrollment is adjusted for independent dropout; this is a transparent simplification.
    enrolled_control = scenario.n_per_arm
    enrolled_treatment = int(np.ceil(scenario.n_per_arm * scenario.allocation_ratio))
    retained_control = max(2, rng.binomial(enrolled_control, 1 - scenario.dropout_rate))
    retained_treatment = max(2, rng.binomial(enrolled_treatment, 1 - scenario.dropout_rate))

    # Site-level additive heterogeneity is drawn as a mean shift, a deliberately simple model.
    control_site_shift = rng.normal(0, scenario.site_heterogeneity_sd)
    treatment_site_shift = rng.normal(0, scenario.site_heterogeneity_sd)

    # Nonadherence attenuates the treatment effect in this intention-to-treat-like toy model.
    effective_effect = scenario.true_effect * (1 - scenario.nonadherence_rate)

    control = rng.normal(control_site_shift, scenario.endpoint_sd, retained_control)
    treatment = rng.normal(
        scenario.true_effect + treatment_site_shift,
        scenario.endpoint_sd,
        retained_treatment,
    )
    if scenario.nonadherence_rate > 0:
        adherent = rng.random(retained_treatment) >= scenario.nonadherence_rate
        treatment = control_site_shift + rng.normal(0, scenario.endpoint_sd, retained_treatment)
        treatment[adherent] += scenario.true_effect

    # Missingness is represented as MCAR for all modes unless an explicit simple MNAR sensitivity
    # is requested. This is a sensitivity demo, not a general missing-data solution.
    if scenario.missingness_mechanism == "MNAR":
        control_missing_p = min(0.95, scenario.dropout_rate * 1.5)
        treatment_missing_p = min(0.95, scenario.dropout_rate * 1.5)
    else:
        control_missing_p = scenario.dropout_rate
        treatment_missing_p = scenario.dropout_rate
    control_keep = rng.random(len(control)) >= control_missing_p
    treatment_keep = rng.random(len(treatment)) >= treatment_missing_p
    control = control[control_keep]
    treatment = treatment[treatment_keep]

    if len(control) < 2 or len(treatment) < 2:
        return {"detected": False, "estimate": np.nan, "p_value": 1.0, "n_control": len(control), "n_treatment": len(treatment)}

    test = stats.ttest_ind(treatment, control, equal_var=False)
    estimate = float(np.mean(treatment) - np.mean(control))
    return {
        "detected": bool(test.pvalue < scenario.alpha),
        "estimate": estimate,
        "p_value": float(test.pvalue),
        "n_control": len(control),
        "n_treatment": len(treatment),
        "effective_effect": float(effective_effect),
    }


def simulate_trial(scenario: TrialScenario) -> dict[str, Any]:
    """Run Monte Carlo trials and return empirical power and diagnostics.

    This is a research/teaching demonstration, not a validated tool for clinical decisions.
    """
    scenario.validate()
    rng = np.random.default_rng(scenario.seed)
    results = [_simulate_once(scenario, rng) for _ in range(scenario.n_simulations)]
    detected = np.array([x["detected"] for x in results], dtype=bool)
    estimates = np.array([x["estimate"] for x in results], dtype=float)
    valid = np.isfinite(estimates)
    power = float(np.mean(detected))
    return {
        "scenario": asdict(scenario),
        "operating_characteristics": {
            "empirical_power": power,
            "monte_carlo_se": float(np.sqrt(power * (1 - power) / scenario.n_simulations)),
            "mean_effect_estimate": float(np.mean(estimates[valid])) if np.any(valid) else None,
            "bias": float(np.mean(estimates[valid]) - scenario.true_effect) if np.any(valid) else None,
            "mean_n_control": float(np.mean([x["n_control"] for x in results])),
            "mean_n_treatment": float(np.mean([x["n_treatment"] for x in results])),
            "n_simulations": scenario.n_simulations,
        },
        "assumptions_and_limitations": [
            "Synthetic two-arm continuous-endpoint model; not clinical evidence.",
            "Welch two-sample t-test; no covariate adjustment or interim monitoring.",
            "Dropout and missingness settings are simplified; MNAR is a stress-test, not a general estimator.",
            "Site heterogeneity is represented by a single random mean shift per arm per simulated trial.",
            "No patient-level data are used.",
        ],
    }
