"""Command-line interface for the clinical trial simulation prototype."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent.workflow import prepare_review_packet
from .reporting.html_report import generate_html_report
from .simulation.engine import simulate_trial
from .simulation.scenarios import TrialScenario


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trial-sim",
        description="Transparent research prototype for clinical trial simulation and protocol review",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. simulate subcommand
    sim = subparsers.add_parser(
        "simulate",
        help="Run a synthetic two-arm continuous-endpoint simulation",
    )
    sim.add_argument("--name", default="demo", help="Scenario display name")
    sim.add_argument("--n-per-arm", type=int, default=100, help="Planned sample size per arm")
    sim.add_argument("--effect", type=float, default=0.3, help="Hypothesized true treatment effect")
    sim.add_argument("--sd", type=float, default=1.0, help="Endpoint standard deviation")
    sim.add_argument("--dropout", type=float, default=0.1, help="Anticipated patient dropout rate")
    sim.add_argument("--nonadherence", type=float, default=0.0, help="Treatment nonadherence rate")
    sim.add_argument("--site-heterogeneity-sd", type=float, default=0.0, help="Site-to-site SD shift")
    sim.add_argument("--missingness", choices=["MCAR", "MAR", "MNAR"], default="MCAR", help="Missingness model")
    sim.add_argument("--n-simulations", type=int, default=1000, help="Monte Carlo iterations")
    sim.add_argument("--seed", type=int, default=42, help="Random number generator seed")
    sim.add_argument("--out", type=Path, required=True, help="Path for JSON simulation results output")
    sim.add_argument("--report", type=Path, default=None, help="HTML report path (default: same path as --out with .html extension)")
    sim.add_argument("--no-sensitivity", action="store_true", help="Skip sensitivity analysis plots in HTML report")

    # 2. report subcommand
    rep = subparsers.add_parser(
        "report",
        help="Generate a reproducible HTML report from an existing simulation results JSON",
    )
    rep.add_argument("--result", type=Path, required=True, help="Path to input simulation results JSON")
    rep.add_argument("--out", type=Path, required=True, help="Path for output HTML report")
    rep.add_argument("--no-sensitivity", action="store_true", help="Skip sensitivity analysis plots")

    # 3. extract subcommand
    extract = subparsers.add_parser(
        "extract",
        help="Extract candidate protocol assumptions for human review",
    )
    extract.add_argument("--protocol", type=Path, required=True, help="Path to input protocol text file")
    extract.add_argument("--out", type=Path, required=True, help="Path for output review packet JSON")

    args = parser.parse_args()

    if args.command == "simulate":
        scenario = TrialScenario(
            name=args.name,
            n_per_arm=args.n_per_arm,
            true_effect=args.effect,
            endpoint_sd=args.sd,
            dropout_rate=args.dropout,
            nonadherence_rate=args.nonadherence,
            site_heterogeneity_sd=args.site_heterogeneity_sd,
            missingness_mechanism=args.missingness,
            n_simulations=args.n_simulations,
            seed=args.seed,
        )
        result = simulate_trial(scenario)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Wrote JSON results to {args.out}")
        print(f"Empirical power: {result['operating_characteristics']['empirical_power']:.3f}")

        report_path = args.report or args.out.with_suffix(".html")
        html = generate_html_report(
            result,
            include_sensitivity=not args.no_sensitivity,
            n_sensitivity_sims=min(250, args.n_simulations),
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(html, encoding="utf-8")
        print(f"Wrote HTML report to {report_path}")

    elif args.command == "report":
        data = json.loads(args.result.read_text(encoding="utf-8"))
        html = generate_html_report(
            data,
            include_sensitivity=not args.no_sensitivity,
            n_sensitivity_sims=250,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(html, encoding="utf-8")
        print(f"Wrote HTML report to {args.out}")

    elif args.command == "extract":
        text = args.protocol.read_text(encoding="utf-8")
        result = prepare_review_packet(text)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Wrote review packet to {args.out}")
        print("Candidate assumptions require human review; no simulation was run.")


if __name__ == "__main__":
    main()
