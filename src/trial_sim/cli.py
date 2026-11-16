"""Command-line interface for the clinical trial simulation prototype."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent.workflow import prepare_review_packet
from .simulation.engine import simulate_trial
from .simulation.scenarios import TrialScenario


def main() -> None:
    parser = argparse.ArgumentParser(prog="trial-sim", description="Transparent research prototype for clinical trial simulation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sim = subparsers.add_parser("simulate", help="Run a synthetic two-arm continuous-endpoint simulation")
    sim.add_argument("--name", default="demo")
    sim.add_argument("--n-per-arm", type=int, default=100)
    sim.add_argument("--effect", type=float, default=0.3)
    sim.add_argument("--sd", type=float, default=1.0)
    sim.add_argument("--dropout", type=float, default=0.1)
    sim.add_argument("--nonadherence", type=float, default=0.0)
    sim.add_argument("--site-heterogeneity-sd", type=float, default=0.0)
    sim.add_argument("--missingness", choices=["MCAR", "MAR", "MNAR"], default="MCAR")
    sim.add_argument("--n-simulations", type=int, default=1000)
    sim.add_argument("--seed", type=int, default=42)
    sim.add_argument("--out", type=Path, required=True)

    extract = subparsers.add_parser("extract", help="Extract candidate protocol assumptions for human review")
    extract.add_argument("--protocol", type=Path, required=True)
    extract.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "simulate":
        scenario = TrialScenario(
            name=args.name, n_per_arm=args.n_per_arm, true_effect=args.effect,
            endpoint_sd=args.sd, dropout_rate=args.dropout,
            nonadherence_rate=args.nonadherence,
            site_heterogeneity_sd=args.site_heterogeneity_sd,
            missingness_mechanism=args.missingness,
            n_simulations=args.n_simulations, seed=args.seed,
        )
        result = simulate_trial(scenario)
    else:
        text = args.protocol.read_text(encoding="utf-8")
        result = prepare_review_packet(text)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    if args.command == "simulate":
        print(f"Empirical power: {result['operating_characteristics']['empirical_power']:.3f}")
    else:
        print("Candidate assumptions require human review; no simulation was run.")
