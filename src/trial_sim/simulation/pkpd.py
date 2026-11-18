"""Two-compartment population pharmacokinetic (PK) and pharmacodynamic (PD) simulation engine.

Supports single and multiple oral/IV dosing regimens, log-normal inter-individual
variability (IIV) on key parameters (CL, Vc, ka), and non-linear sigmoidal Emax /
Hill pharmacodynamic target engagement and biomarker suppression modeling.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class PKParameters:
    """Two-compartment pharmacokinetic structural parameters."""
    cl: float = 5.0          # Clearance (L/h)
    vc: float = 20.0         # Central volume of distribution (L)
    q: float = 8.0           # Intercompartmental clearance (L/h)
    vp: float = 40.0         # Peripheral volume of distribution (L)
    ka: float = 1.2          # First-order absorption rate constant (1/h)
    bioavailability: float = 0.85  # Fraction absorbed (F)
    
    # IIV coefficients of variation (CV% as fractions, e.g. 0.25 = 25% CV)
    omega_cl: float = 0.25
    omega_vc: float = 0.20
    omega_ka: float = 0.30


@dataclass
class PDParameters:
    """Sigmoidal Emax / Hill pharmacodynamic parameters."""
    baseline_biomarker: float = 100.0   # Baseline biomarker level (e.g. 100% or ng/mL)
    emax: float = 95.0                  # Maximum biomarker inhibition (%) or effect
    ec50: float = 1.5                   # Drug concentration at half-maximal effect (mg/L)
    gamma: float = 1.5                  # Hill cooperativity coefficient
    model_type: str = "inhibitory"      # 'inhibitory' (suppression) or 'stimulatory'


@dataclass
class DosingRegimen:
    """Dosing schedule specification."""
    dose_mg: float = 100.0
    route: str = "oral"        # 'oral' or 'iv_bolus'
    interval_hours: float = 24.0  # Dosing interval tau (e.g. 24 = QD, 12 = BID, 168 = QW)
    num_doses: int = 7           # Number of repeated doses (e.g. 7 doses = 7 days for QD)


@dataclass
class SubjectPKPDProfile:
    """Simulated PK and PD time-course for an individual subject."""
    subject_id: int
    cl_ind: float
    vc_ind: float
    ka_ind: float
    time_hours: List[float]
    conc_central_mg_l: List[float]
    conc_peripheral_mg_l: List[float]
    biomarker_response: List[float]
    target_engagement_pct: List[float]
    cmax_ss: float
    ctrough_ss: float
    auc_tau: float
    tmax_ss: float
    time_above_ec90_pct: float


@dataclass
class PopulationPKPDResult:
    """Aggregated population simulation results and exposure statistics."""
    parameters_pk: Dict[str, Any]
    parameters_pd: Dict[str, Any]
    regimen: Dict[str, Any]
    n_subjects: int
    time_grid: List[float]
    
    # Summary PK percentiles (mg/L) across time
    median_conc: List[float]
    p05_conc: List[float]
    p95_conc: List[float]
    
    # Summary PD target engagement (%) across time
    median_target_engagement: List[float]
    p05_target_engagement: List[float]
    p95_target_engagement: List[float]
    
    # Key exposure metrics (mean +- std and median [IQR])
    metrics: Dict[str, Dict[str, float]]
    
    # Representative individual subject profiles (first 5 subjects for plotting)
    individual_profiles: List[SubjectPKPDProfile] = field(default_factory=list)


def _micro_rate_constants(cl: float, vc: float, q: float, vp: float) -> Tuple[float, float, float, float, float]:
    """Calculate micro rate constants and hybrid exponential disposition constants."""
    k10 = cl / vc
    k12 = q / vc
    k21 = q / vp
    
    # Hybrid rate constants alpha and beta (roots of quadratic characteristic eq)
    sum_k = k10 + k12 + k21
    prod_k = k10 * k21
    radicand = max(0.0, sum_k ** 2 - 4.0 * prod_k)
    sqrt_rad = math.sqrt(radicand)
    
    alpha = 0.5 * (sum_k + sqrt_rad)
    beta = 0.5 * (sum_k - sqrt_rad)
    
    return k10, k12, k21, alpha, beta


def simulate_subject_pkpd(
    subject_id: int,
    cl: float,
    vc: float,
    q: float,
    vp: float,
    ka: float,
    bioavailability: float,
    pd_params: PDParameters,
    regimen: DosingRegimen,
    time_points: np.ndarray,
) -> SubjectPKPDProfile:
    """Simulate time-course PK and PD for a single patient using analytical multi-dose equations."""
    k10, k12, k21, alpha, beta = _micro_rate_constants(cl, vc, q, vp)
    dose = regimen.dose_mg * (bioavailability if regimen.route == "oral" else 1.0)
    tau = regimen.interval_hours
    n_doses = regimen.num_doses
    
    conc_c = np.zeros_like(time_points, dtype=float)
    conc_p = np.zeros_like(time_points, dtype=float)
    
    # Analytical superposition across doses
    for d_idx in range(n_doses):
        t_dose = d_idx * tau
        mask = time_points >= t_dose
        t_rel = time_points[mask] - t_dose
        
        if regimen.route == "oral":
            # 2-compartment oral absorption model
            denom_alpha = (ka - alpha) if abs(ka - alpha) > 1e-6 else 1e-6
            denom_beta = (ka - beta) if abs(ka - beta) > 1e-6 else 1e-6
            
            coef_alpha = (dose * ka / vc) * (k21 - alpha) / (denom_alpha * (beta - alpha))
            coef_beta = (dose * ka / vc) * (k21 - beta) / (denom_beta * (alpha - beta))
            coef_ka = - (coef_alpha + coef_beta)
            
            conc_c[mask] += coef_alpha * np.exp(-alpha * t_rel) + coef_beta * np.exp(-beta * t_rel) + coef_ka * np.exp(-ka * t_rel)
            
            # Peripheral compartment
            coef_p_alpha = (dose * ka * k12 / vp) / (denom_alpha * (beta - alpha))
            coef_p_beta = (dose * ka * k12 / vp) / (denom_beta * (alpha - beta))
            coef_p_ka = - (coef_p_alpha + coef_p_beta)
            conc_p[mask] += coef_p_alpha * np.exp(-alpha * t_rel) + coef_p_beta * np.exp(-beta * t_rel) + coef_p_ka * np.exp(-ka * t_rel)
            
        else:
            # IV bolus 2-compartment model
            coef_alpha = (dose / vc) * (alpha - k21) / (alpha - beta)
            coef_beta = (dose / vc) * (k21 - beta) / (alpha - beta)
            conc_c[mask] += coef_alpha * np.exp(-alpha * t_rel) + coef_beta * np.exp(-beta * t_rel)
            
            coef_p = (dose * k12 / vp) / (alpha - beta)
            conc_p[mask] += coef_p * (np.exp(-beta * t_rel) - np.exp(-alpha * t_rel))
            
    conc_c = np.maximum(conc_c, 0.0)
    conc_p = np.maximum(conc_p, 0.0)
    
    # PD Target Engagement / Biomarker calculation
    ec50 = max(pd_params.ec50, 1e-6)
    gamma = pd_params.gamma
    emax = pd_params.emax
    base_bm = pd_params.baseline_biomarker
    
    # Sigmoidal Hill target engagement (%)
    conc_gamma = conc_c ** gamma
    ec50_gamma = ec50 ** gamma
    te_pct = 100.0 * (conc_gamma / (ec50_gamma + conc_gamma))
    
    # Biomarker response
    if pd_params.model_type == "inhibitory":
        biomarker = base_bm * (1.0 - (emax / 100.0) * (conc_gamma / (ec50_gamma + conc_gamma)))
    else:
        biomarker = base_bm * (1.0 + (emax / 100.0) * (conc_gamma / (ec50_gamma + conc_gamma)))
        
    # Steady state exposure metrics (in the final dosing interval)
    ss_start = (n_doses - 1) * tau
    ss_end = n_doses * tau
    ss_mask = (time_points >= ss_start) & (time_points <= ss_end)
    
    if np.sum(ss_mask) > 1:
        ss_times = time_points[ss_mask]
        ss_conc = conc_c[ss_mask]
        cmax_ss = float(np.max(ss_conc))
        ctrough_ss = float(ss_conc[-1])
        tmax_idx = np.argmax(ss_conc)
        tmax_ss = float(ss_times[tmax_idx] - ss_start)
        # Trapezoidal AUC
        auc_tau = float(np.trapezoid(ss_conc, ss_times))
        
        # Time above EC90 (where EC90 = EC50 * (90/10)^(1/gamma))
        ec90 = ec50 * (9.0 ** (1.0 / max(gamma, 0.1)))
        time_above = np.mean(ss_conc >= ec90) * 100.0
    else:
        cmax_ss = float(np.max(conc_c))
        ctrough_ss = float(conc_c[-1])
        tmax_ss = 0.0
        auc_tau = float(np.trapezoid(conc_c, time_points))
        time_above = 0.0
        
    return SubjectPKPDProfile(
        subject_id=subject_id,
        cl_ind=float(cl),
        vc_ind=float(vc),
        ka_ind=float(ka),
        time_hours=time_points.tolist(),
        conc_central_mg_l=conc_c.tolist(),
        conc_peripheral_mg_l=conc_p.tolist(),
        biomarker_response=biomarker.tolist(),
        target_engagement_pct=te_pct.tolist(),
        cmax_ss=cmax_ss,
        ctrough_ss=ctrough_ss,
        auc_tau=auc_tau,
        tmax_ss=tmax_ss,
        time_above_ec90_pct=float(time_above),
    )


def simulate_population_pkpd(
    pk_params: Optional[PKParameters] = None,
    pd_params: Optional[PDParameters] = None,
    regimen: Optional[DosingRegimen] = None,
    n_subjects: int = 100,
    seed: int = 42,
    time_step_hours: float = 0.25,
) -> PopulationPKPDResult:
    """Execute full Monte Carlo population PK/PD simulation with IIV."""
    pk = pk_params or PKParameters()
    pd = pd_params or PDParameters()
    reg = regimen or DosingRegimen()
    
    total_time = reg.num_doses * reg.interval_hours + reg.interval_hours
    time_grid = np.arange(0.0, total_time + time_step_hours / 2.0, time_step_hours)
    
    rng = np.random.default_rng(seed)
    
    # Sample individual parameters with log-normal IIV
    # parameter_i = parameter_pop * exp(eta), eta ~ N(0, omega^2)
    eta_cl = rng.normal(0.0, pk.omega_cl, n_subjects)
    eta_vc = rng.normal(0.0, pk.omega_vc, n_subjects)
    eta_ka = rng.normal(0.0, pk.omega_ka, n_subjects)
    
    cl_indiv = pk.cl * np.exp(eta_cl)
    vc_indiv = pk.vc * np.exp(eta_vc)
    ka_indiv = pk.ka * np.exp(eta_ka)
    
    all_conc = np.zeros((n_subjects, len(time_grid)))
    all_te = np.zeros((n_subjects, len(time_grid)))
    
    cmax_list = []
    ctrough_list = []
    auc_list = []
    tmax_list = []
    time_above_list = []
    profiles: List[SubjectPKPDProfile] = []
    
    for i in range(n_subjects):
        prof = simulate_subject_pkpd(
            subject_id=i + 1,
            cl=cl_indiv[i],
            vc=vc_indiv[i],
            q=pk.q,
            vp=pk.vp,
            ka=ka_indiv[i],
            bioavailability=pk.bioavailability,
            pd_params=pd,
            regimen=reg,
            time_points=time_grid,
        )
        all_conc[i, :] = prof.conc_central_mg_l
        all_te[i, :] = prof.target_engagement_pct
        cmax_list.append(prof.cmax_ss)
        ctrough_list.append(prof.ctrough_ss)
        auc_list.append(prof.auc_tau)
        tmax_list.append(prof.tmax_ss)
        time_above_list.append(prof.time_above_ec90_pct)
        
        # Save first 8 individual trajectories for plotting
        if i < 8:
            profiles.append(prof)
            
    # Calculate population summary percentiles
    median_conc = np.median(all_conc, axis=0).tolist()
    p05_conc = np.percentile(all_conc, 5, axis=0).tolist()
    p95_conc = np.percentile(all_conc, 95, axis=0).tolist()
    
    median_te = np.median(all_te, axis=0).tolist()
    p05_te = np.percentile(all_te, 5, axis=0).tolist()
    p95_te = np.percentile(all_te, 95, axis=0).tolist()
    
    def _stats(arr: List[float]) -> Dict[str, float]:
        a = np.array(arr)
        return {
            "mean": float(np.mean(a)),
            "std": float(np.std(a)),
            "median": float(np.median(a)),
            "p25": float(np.percentile(a, 25)),
            "p75": float(np.percentile(a, 75)),
            "cv_pct": float(100.0 * np.std(a) / max(np.mean(a), 1e-9)),
        }
        
    metrics = {
        "cmax_ss": _stats(cmax_list),
        "ctrough_ss": _stats(ctrough_list),
        "auc_tau": _stats(auc_list),
        "tmax_ss": _stats(tmax_list),
        "time_above_ec90_pct": _stats(time_above_list),
    }
    
    return PopulationPKPDResult(
        parameters_pk=asdict(pk),
        parameters_pd=asdict(pd),
        regimen=asdict(reg),
        n_subjects=n_subjects,
        time_grid=time_grid.tolist(),
        median_conc=median_conc,
        p05_conc=p05_conc,
        p95_conc=p95_conc,
        median_target_engagement=median_te,
        p05_target_engagement=p05_te,
        p95_target_engagement=p95_te,
        metrics=metrics,
        individual_profiles=profiles,
    )
