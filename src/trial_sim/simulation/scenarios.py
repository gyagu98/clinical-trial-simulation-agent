"""
Trial simulation scenario definitions.
All simulated values are synthetic or user-specified and are not clinical recommendations.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TrialScenario:
    """User-configurable parameters for a two-arm, normally distributed endpoint trial."""
    name: str
    n_per_arm: int
    true_effect: float
    endpoint_sd: float
    alpha: float = 0.05
    allocation_ratio: float = 1.0
    dropout_rate: float = 0.0
    nonadherence_rate: float = 0.0
    recruitment_months: int = 12
    site_heterogeneity_sd: float = 0.0
    missingness_mechanism: str = "MCAR"
    seed: int = 42
    n_simulations: int = 1000

    def validate(self) -> None:
        if self.n_per_arm < 2:
            raise ValueError("n_per_arm must be >= 2")
        if self.endpoint_sd <= 0:
            raise ValueError("endpoint_sd must be > 0")
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        if self.allocation_ratio <= 0:
            raise ValueError("allocation_ratio must be > 0")
        for field_name in ("dropout_rate", "nonadherence_rate"):
            val = getattr(self, field_name)
            if not 0 <= val < 1:
                raise ValueError(f"{field_name} must be in [0, 1)")
        if self.recruitment_months < 1:
            raise ValueError("recruitment_months must be >= 1")
        if self.site_heterogeneity_sd < 0:
            raise ValueError("site_heterogeneity_sd must be >= 0")
        if self.missingness_mechanism not in {"MCAR", "MAR", "MNAR"}:
            raise ValueError("missingness_mechanism must be MCAR, MAR, or MNAR")
        if self.n_simulations < 1:
            raise ValueError("n_simulations must be >= 1")
