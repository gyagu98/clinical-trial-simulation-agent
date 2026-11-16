import pytest

from trial_sim.simulation.engine import simulate_trial
from trial_sim.simulation.scenarios import TrialScenario


def test_simulation_reproducible():
    scenario = TrialScenario(
        name="repro", n_per_arm=50, true_effect=0.4, endpoint_sd=1.0,
        dropout_rate=0.15, n_simulations=100, seed=123,
    )
    first = simulate_trial(scenario)
    second = simulate_trial(scenario)
    assert first["operating_characteristics"] == second["operating_characteristics"]


def test_large_effect_has_higher_power_than_null():
    null = TrialScenario(name="null", n_per_arm=80, true_effect=0, endpoint_sd=1, n_simulations=1000, seed=4)
    alt = TrialScenario(name="alt", n_per_arm=80, true_effect=0.6, endpoint_sd=1, n_simulations=1000, seed=4)
    assert simulate_trial(alt)["operating_characteristics"]["empirical_power"] > simulate_trial(null)["operating_characteristics"]["empirical_power"]


def test_invalid_dropout_rejected():
    scenario = TrialScenario(name="bad", n_per_arm=10, true_effect=0.3, endpoint_sd=1, dropout_rate=1)
    with pytest.raises(ValueError):
        simulate_trial(scenario)


def test_assumptions_are_returned():
    scenario = TrialScenario(name="demo", n_per_arm=20, true_effect=0.2, endpoint_sd=1, n_simulations=10)
    result = simulate_trial(scenario)
    assert len(result["assumptions_and_limitations"]) >= 4
