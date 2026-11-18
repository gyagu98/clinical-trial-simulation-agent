"""Command-line interface for the clinical trial simulation and pharmacometrics prototype."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .agent.workflow import prepare_review_packet
from .reporting.html_report import generate_html_report
from .reporting.pkpd_report import generate_pkpd_html_report
from .simulation.engine import simulate_trial
from .simulation.pkpd import (
    DosingRegimen,
    PDParameters,
    PKParameters,
    simulate_population_pkpd,
)
from .simulation.scenarios import TrialScenario


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="trial-sim",
        description="Transparent research prototype for clinical trial simulation, protocol review, and population PK/PD pharmacometrics",
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

    # 4. simulate-pkpd subcommand (Pharmacometrics & Population PK/PD)
    pkpd = subparsers.add_parser(
        "simulate-pkpd",
        help="Run a two-compartment population PK/PD simulation with IIV and sigmoidal Emax target engagement",
    )
    pkpd.add_argument("--dose", type=float, default=100.0, help="Dose amount in mg (default: 100.0)")
    pkpd.add_argument("--route", choices=["oral", "iv_bolus"], default="oral", help="Administration route")
    pkpd.add_argument("--interval", type=float, default=24.0, help="Dosing interval tau in hours (default: 24.0)")
    pkpd.add_argument("--num-doses", type=int, default=7, help="Number of doses (default: 7)")
    pkpd.add_argument("--n-subjects", type=int, default=100, help="Simulated population size (default: 100)")
    pkpd.add_argument("--cl", type=float, default=5.0, help="Clearance in L/h (default: 5.0)")
    pkpd.add_argument("--vc", type=float, default=20.0, help="Central volume in L (default: 20.0)")
    pkpd.add_argument("--q", type=float, default=8.0, help="Intercompartmental clearance in L/h (default: 8.0)")
    pkpd.add_argument("--vp", type=float, default=40.0, help="Peripheral volume in L (default: 40.0)")
    pkpd.add_argument("--ka", type=float, default=1.2, help="Absorption rate in 1/h (default: 1.2)")
    pkpd.add_argument("--emax", type=float, default=95.0, help="Maximal PD biomarker effect %% (default: 95.0)")
    pkpd.add_argument("--ec50", type=float, default=1.5, help="Potency EC50 in mg/L (default: 1.5)")
    pkpd.add_argument("--gamma", type=float, default=1.5, help="Hill coefficient (default: 1.5)")
    pkpd.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    pkpd.add_argument("--out", type=Path, required=True, help="Path for output JSON results")
    pkpd.add_argument("--report", type=Path, default=None, help="Path for output HTML report (default: --out with .html)")

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

    elif args.command == "simulate-pkpd":
        pk_params = PKParameters(
            cl=args.cl,
            vc=args.vc,
            q=args.q,
            vp=args.vp,
            ka=args.ka,
        )
        pd_params = PDParameters(
            emax=args.emax,
            ec50=args.ec50,
            gamma=args.gamma,
        )
        regimen = DosingRegimen(
            dose_mg=args.dose,
            route=args.route,
            interval_hours=args.interval,
            num_doses=args.num_doses,
        )
        res = simulate_population_pkpd(
            pk_params=pk_params,
            pd_params=pd_params,
            regimen=regimen,
            n_subjects=args.n_subjects,
            seed=args.seed,
        )
        
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # Serialize to json (excluding huge individual profile time arrays for compactness in json)
        res_dict = {
            "parameters_pk": res.parameters_pk,
            "parameters_pd": res.parameters_pd,
            "regimen": res.regimen,
            "n_subjects": res.n_subjects,
            "metrics": res.metrics,
            "steady_state_summary": {
                "median_cmax_mg_l": res.metrics["cmax_ss"]["median"],
                "median_ctrough_mg_l": res.metrics["ctrough_ss"]["median"],
                "median_auc_tau_mg_h_l": res.metrics["auc_tau"]["median"],
                "median_time_above_ec90_pct": res.metrics["time_above_ec90_pct"]["median"],
            }
        }
        args.out.write_text(json.dumps(res_dict, indent=2), encoding="utf-8")
        print(f"Wrote Population PK/PD JSON results to {args.out}")
        print(f"Steady-state median Cmax: {res.metrics['cmax_ss']['median']:.2f} mg/L, Ctrough: {res.metrics['ctrough_ss']['median']:.2f} mg/L")
        print(f"Steady-state target coverage (>EC90): {res.metrics['time_above_ec90_pct']['median']:.1f}%")

        report_path = args.report or args.out.with_suffix(".html")
        html = generate_pkpd_html_report(res)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(html, encoding="utf-8")
        print(f"Wrote Population PK/PD HTML report to {report_path}")


if __name__ == "__main__":
    main()
