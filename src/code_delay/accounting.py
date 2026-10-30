"""CoDE accounting: Eqs. (1)-(10) of the article.

Every quantity is a present value in USD at the planned service date (month 0).
Months t = 1..tau are the months of the delay; d_t = (1 + r)^(-t/12).
The three perspectives are returned side by side and are never summed (Eq. 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd

from .parameters import PROFILES, Scenario, _fraction, _months, _non_negative


# ---------------------------------------------------------------------------
# Discounting and the capital deployment profile
# ---------------------------------------------------------------------------

def discount_factor(month: float, annual_rate: float) -> float:
    """d_t = (1 + r)^(-t/12)."""
    if month < 0:
        raise ValueError("month must be non-negative")
    if annual_rate <= -1.0:
        raise ValueError("annual_rate must exceed -1")
    return (1.0 + annual_rate) ** (-month / 12.0)


def deployment_fraction(month: int, delay_months: int, profile: str, peak: float) -> float:
    """alpha_t for month t of a delay of tau months.

    With build progress x_t = min(t / tau, 1): static a, linear a x_t,
    front-loaded a min(1, 2 x_t), back-loaded a x_t^2.
    """
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of {PROFILES}, got {profile!r}")
    _fraction(peak, "peak")
    if delay_months <= 0:
        return 0.0
    if month < 1:
        raise ValueError("month must be at least 1")
    x = min(month / delay_months, 1.0)
    shape = {"static": 1.0, "linear": x, "front_loaded": min(1.0, 2.0 * x), "back_loaded": x * x}[profile]
    return peak * shape


@lru_cache(maxsize=65536)
def _annuity(delay_months: int, annual_rate: float) -> float:
    """sum_{t=1}^{tau} d_t."""
    return math.fsum(discount_factor(t, annual_rate) for t in range(1, delay_months + 1))


@lru_cache(maxsize=65536)
def _deployment_annuity(delay_months: int, annual_rate: float, profile: str, peak: float) -> float:
    """sum_{t=1}^{tau} d_t alpha_t."""
    return math.fsum(discount_factor(t, annual_rate) * deployment_fraction(t, delay_months, profile, peak)
                     for t in range(1, delay_months + 1))


# ---------------------------------------------------------------------------
# Eq. (1): the CoDE vector
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CodeVector:
    """C^CoDE = (C^priv, C^rate, C^soc), Eq. (1). The components are not added."""

    private: float
    ratepayer: float
    social: float

    def as_dict(self) -> dict[str, float]:
        return {"private_usd": self.private, "ratepayer_usd": self.ratepayer, "social_usd": self.social}


# ---------------------------------------------------------------------------
# Eq. (2): private perspective
# ---------------------------------------------------------------------------

def private_monthly(scenario: Scenario, delay_months: int | None = None,
                    it_capacity_mw: float | None = None) -> pd.DataFrame:
    """Month-by-month terms of Eq. (2), undiscounted and discounted (USD).

    Columns: month, discount_factor, deployment_fraction, lost_margin, carrying,
    contract_penalty, mitigation_premium, total, and the same with a ``pv_`` prefix.
    """
    tau = scenario.delay_months if delay_months is None else _months(delay_months, "delay_months")
    p_it = scenario.project.it_capacity_mw if it_capacity_mw is None else _non_negative(it_capacity_mw, "it_capacity_mw")
    pi = scenario.private
    r = scenario.discount_rate_annual
    months = np.arange(1, tau + 1)
    d = np.array([discount_factor(t, r) for t in months], dtype=float)
    alpha = np.array([deployment_fraction(int(t), tau, pi.deployment_profile, pi.deployment_peak) for t in months],
                     dtype=float)
    margin = np.full(tau, p_it * pi.realization_probability * (1.0 - pi.substitution_fraction)
                     * pi.gross_value_usd_per_mw_it_month * pi.operating_margin)
    carrying = p_it * pi.committed_capital_usd_per_mw_it * pi.committed_capital_fraction * alpha \
        * pi.carrying_rate_annual / 12.0
    contract = np.full(tau, p_it * pi.contract_penalty_usd_per_mw_it_month)
    mitigation = np.full(tau, p_it * pi.mitigation_premium_usd_per_mw_it_month)
    table = pd.DataFrame({"month": months, "discount_factor": d, "deployment_fraction": alpha,
                          "lost_margin": margin, "carrying": carrying,
                          "contract_penalty": contract, "mitigation_premium": mitigation})
    table["total"] = table[["lost_margin", "carrying", "contract_penalty", "mitigation_premium"]].sum(axis=1)
    for col in ("lost_margin", "carrying", "contract_penalty", "mitigation_premium", "total"):
        table["pv_" + col] = table[col] * table["discount_factor"]
    return table


def private_cost(scenario: Scenario, delay_months: int | None = None,
                 it_capacity_mw: float | None = None) -> dict[str, float]:
    """C^priv(P_I, tau), Eq. (2), with its four components (USD, present value)."""
    tau = scenario.delay_months if delay_months is None else _months(delay_months, "delay_months")
    p_it = scenario.project.it_capacity_mw if it_capacity_mw is None else _non_negative(it_capacity_mw, "it_capacity_mw")
    pi = scenario.private
    r = scenario.discount_rate_annual
    annuity = _annuity(tau, r)
    lost_margin = p_it * pi.realization_probability * (1.0 - pi.substitution_fraction) \
        * pi.gross_value_usd_per_mw_it_month * pi.operating_margin * annuity
    carrying = p_it * pi.committed_capital_usd_per_mw_it * pi.committed_capital_fraction \
        * pi.carrying_rate_annual / 12.0 * _deployment_annuity(tau, r, pi.deployment_profile, pi.deployment_peak)
    contract = p_it * pi.contract_penalty_usd_per_mw_it_month * annuity
    mitigation = p_it * pi.mitigation_premium_usd_per_mw_it_month * annuity
    return {"lost_margin": lost_margin, "carrying": carrying, "contract_penalty": contract,
            "mitigation_premium": mitigation, "total": lost_margin + carrying + contract + mitigation}


# ---------------------------------------------------------------------------
# Eq. (3): ratepayer perspective
# ---------------------------------------------------------------------------

def ratepayer_cost(scenario: Scenario, delay_months: int | None = None) -> dict[str, float]:
    """C^rate(tau), Eq. (3): expected utility carrying cost plus expected stranding (USD).

    At tau = 0 the carrying sum is empty and the stranding term remains.
    """
    tau = scenario.delay_months if delay_months is None else _months(delay_months, "delay_months")
    rp = scenario.ratepayer
    r = scenario.discount_rate_annual
    p_grid = scenario.project.grid_mw
    phi_u, phi_s = scenario.event_probabilities
    carrying = _annuity(tau, r) * p_grid * rp.upgrade_cost_usd_per_grid_mw * rp.utility_carrying_rate_annual \
        * rp.residual_share * phi_u / 12.0
    stranding = discount_factor(tau, r) * p_grid * rp.upgrade_cost_usd_per_grid_mw * rp.residual_share * phi_u * phi_s
    return {"carrying": carrying, "stranding": stranding, "total": carrying + stranding,
            "financing_probability": phi_u, "stranding_probability": phi_s}


def ratepayer_delay_cost(scenario: Scenario, delay_months: int | None = None) -> float:
    """Delay-attributable ratepayer cost Delta C^rate(tau) = C^rate(tau) - C^rate(0) (USD)."""
    tau = scenario.delay_months if delay_months is None else delay_months
    return ratepayer_cost(scenario, tau)["total"] - ratepayer_cost(scenario, 0)["total"]


# ---------------------------------------------------------------------------
# Eqs. (4)-(5): social perspective of a pathway
# ---------------------------------------------------------------------------

def _monthly_array(values, tau: int, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = np.full(tau, float(arr))
    if arr.shape != (tau,):
        raise ValueError(f"{name} must be a scalar or have one value per month ({tau})")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    return arr


def social_cost(pathway_probability: float, annual_rate: float, delay_months: int,
                emissions_usd=0.0, reliability_usd=0.0, local_usd=0.0, discount: bool = True) -> float:
    """C^soc(h), Eq. (4): p_h sum_t d_t (C^em_t + C^rel_t + C^loc_t) (USD).

    Each monthly term is a scalar (the same every month) or one value per month.
    ``discount=False`` sets d_t = 1 (for short windows; see docs/formulation.md).
    """
    p_h = _fraction(pathway_probability, "pathway_probability")
    tau = _months(delay_months, "delay_months")
    total = _monthly_array(emissions_usd, tau, "emissions_usd") + _monthly_array(reliability_usd, tau, "reliability_usd") \
        + _monthly_array(local_usd, tau, "local_usd")
    d = np.array([discount_factor(t, annual_rate) if discount else 1.0 for t in range(1, tau + 1)])
    return p_h * float(np.sum(d * total))


def emissions_social_cost(pathway_probability: float, annual_rate: float, delay_months: int,
                          energy_mwh_per_month, pathway_t_per_mwh, counterfactual_t_per_mwh,
                          social_cost_usd_per_t, discount: bool = True) -> float:
    """C^soc,em(h), Eq. (5): p_h sum_t d_t E_t [eps_h(t) - eps_0(t)] v_t (USD).

    A negative factor difference is kept, so the result can be an avoided damage.
    """
    tau = _months(delay_months, "delay_months")
    energy = _monthly_array(energy_mwh_per_month, tau, "energy_mwh_per_month")
    if np.any(energy < 0):
        raise ValueError("energy_mwh_per_month must be non-negative")
    diff = _monthly_array(pathway_t_per_mwh, tau, "pathway_t_per_mwh") \
        - _monthly_array(counterfactual_t_per_mwh, tau, "counterfactual_t_per_mwh")
    scc = _monthly_array(social_cost_usd_per_t, tau, "social_cost_usd_per_t")
    return social_cost(pathway_probability, annual_rate, tau, emissions_usd=energy * diff * scc, discount=discount)


# ---------------------------------------------------------------------------
# Eq. (1) assembled, and Eq. (6): delay cost intensity
# ---------------------------------------------------------------------------

def code_vector(scenario: Scenario, social_usd: float = 0.0) -> CodeVector:
    """C^CoDE for a scenario; ``social_usd`` is C^soc of the pathway that fills the delay (Eqs. 4-5)."""
    return CodeVector(private=private_cost(scenario)["total"], ratepayer=ratepayer_cost(scenario)["total"],
                      social=float(social_usd))


def delay_cost_intensity(scenario: Scenario) -> dict[str, float]:
    """DCI, Eq. (6): private in USD per MW-IT-month, ratepayer (delay differential) in USD per grid-MW-month.

    Undefined (NaN) when the delay or the capacity is zero.
    """
    tau = scenario.delay_months
    p_it = scenario.project.it_capacity_mw
    p_grid = scenario.project.grid_mw
    priv = private_cost(scenario)["total"]
    d_rate = ratepayer_delay_cost(scenario)
    return {"private_usd_per_mw_it_month": priv / (p_it * tau) if p_it > 0 and tau > 0 else math.nan,
            "ratepayer_usd_per_grid_mw_month": d_rate / (p_grid * tau) if p_grid > 0 and tau > 0 else math.nan}


# ---------------------------------------------------------------------------
# Eqs. (7)-(8): avoided cost, BEAP and the net-benefit test
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AvoidedCost:
    """Avoided costs of an option m that shortens the delay (Eq. 7)."""

    private: float     # Delta C^priv_m = BEAP
    ratepayer: float   # Delta C^rate_m (the tau = 0 stock cancels)

    @property
    def beap(self) -> float:
        """Break-even acceleration payment: the scalar Delta C^priv_m."""
        return self.private


def avoided_cost(scenario: Scenario, shortened_delay_months: int) -> AvoidedCost:
    """Eq. (7): the delay falls from tau_0 = scenario.delay_months to tau_1."""
    tau0 = scenario.delay_months
    tau1 = _months(shortened_delay_months, "shortened_delay_months")
    if tau1 > tau0:
        raise ValueError("shortened_delay_months cannot exceed the delay")
    return AvoidedCost(private=private_cost(scenario)["total"] - private_cost(scenario, tau1)["total"],
                       ratepayer=ratepayer_cost(scenario)["total"] - ratepayer_cost(scenario, tau1)["total"])


@dataclass(frozen=True)
class NetBenefit:
    """Eq. (8) and the distributional condition that follows it."""

    value: float                         # Delta C^priv + Delta C^rate - C^add - Delta C^soc
    potentially_welfare_improving: bool  # value > 0
    privately_worthwhile: bool           # BEAP >= C^add
    implementation_cost_bound: float     # strict upper bound: Eq. (8) holds iff C^add is below it


def net_benefit(avoided_private: float, avoided_ratepayer: float, implementation_cost: float,
                added_social: float) -> NetBenefit:
    """Eq. (8): option m is potentially welfare-improving when the value is positive.

    ``added_social`` is Delta C^soc_m = C^soc(m) - C^soc(on time), normally positive.
    """
    value = avoided_private + avoided_ratepayer - implementation_cost - added_social
    return NetBenefit(value=value, potentially_welfare_improving=value > 0,
                      privately_worthwhile=avoided_private >= implementation_cost,
                      implementation_cost_bound=avoided_private + avoided_ratepayer - added_social)


def distributionally_acceptable(developer_payment: float, implementation_cost: float, added_social: float) -> bool:
    """The developer's payment covers C^add_m plus compensation for Delta C^soc_m."""
    return developer_payment >= implementation_cost + max(added_social, 0.0)


# ---------------------------------------------------------------------------
# Eq. (9): staged service
# ---------------------------------------------------------------------------

def staged_private_cost(scenario: Scenario, first_service_months: int, served_fraction: float,
                        revenue_equivalent: Callable[[float], float] | None = None) -> dict[str, float]:
    """C^priv_stage, Eq. (9): a fraction f is served after tau_e < tau_0, the rest at tau_0.

    g(f) (``revenue_equivalent``) scales both the margin and the carrying term; g(f) = f by default.
    Returns the staged cost, the unstaged cost and the private value of partial service.
    """
    tau0 = scenario.delay_months
    tau_e = _months(first_service_months, "first_service_months")
    if tau_e > tau0:
        raise ValueError("first_service_months cannot exceed the delay")
    f = _fraction(served_fraction, "served_fraction")
    g = f if revenue_equivalent is None else _fraction(revenue_equivalent(f), "revenue_equivalent(f)")
    p_it = scenario.project.it_capacity_mw
    staged = private_cost(scenario, tau_e, g * p_it)["total"] + private_cost(scenario, tau0, (1.0 - g) * p_it)["total"]
    unstaged = private_cost(scenario)["total"]
    return {"staged": staged, "unstaged": unstaged, "value_of_partial_service": unstaged - staged,
            "revenue_equivalent_fraction": g}


# ---------------------------------------------------------------------------
# Eq. (10): realization decomposition and elasticity
# ---------------------------------------------------------------------------

def realization_decomposition(scenario: Scenario, delay_months: int | None = None) -> dict[str, float]:
    """C^priv = q A_tau + B_tau (+ Pi_tau) and eta_{C,q}, Eq. (10).

    A_tau collects the terms weighted by q, B_tau is the carrying cost, Pi_tau the
    unweighted contract and mitigation terms (zero when they are not used).
    """
    tau = scenario.delay_months if delay_months is None else delay_months
    q = scenario.private.realization_probability
    parts = private_cost(scenario, tau)
    a_tau = parts["lost_margin"] / q if q > 0 else private_cost(scenario.with_realization(1.0), tau)["lost_margin"]
    b_tau = parts["carrying"]
    pi_tau = parts["contract_penalty"] + parts["mitigation_premium"]
    total = q * a_tau + b_tau + pi_tau
    return {"A": a_tau, "B": b_tau, "Pi": pi_tau, "q": q, "total": total,
            "elasticity": q * a_tau / total if total > 0 else math.nan}
