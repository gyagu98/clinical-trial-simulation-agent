"""Clinical trial simulation and population PK/PD modeling package."""

from .simulation.engine import simulate_trial
from .simulation.pkpd import (
    DosingRegimen,
    PDParameters,
    PKParameters,
    PopulationPKPDResult,
    simulate_population_pkpd,
)
from .simulation.scenarios import TrialScenario

__version__ = "0.2.0"

__all__ = [
    "TrialScenario",
    "simulate_trial",
    "PKParameters",
    "PDParameters",
    "DosingRegimen",
    "PopulationPKPDResult",
    "simulate_population_pkpd",
]
