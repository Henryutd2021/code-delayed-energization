"""Delay-realization dependence stress test (Section III of the article).

The realization probability is conditioned on the delay:

    q_beta(tau) = min{1, q_anchor * exp[-beta (tau - tau_anchor) / 12]},

with beta in 1/yr. All curves pass through q_anchor at the anchor delay. The private
cost then decomposes as in Eq. (10), and the ratepayer level moves with q through
phi_s (milestone financing) or phi_u (realization-linked financing).
"""

from __future__ import annotations

import math

import pandas as pd

from .accounting import private_cost, ratepayer_cost, realization_decomposition
from .parameters import Scenario, _finite, _fraction, _months


def realization_curve(delay_months: float, beta_per_year: float, q_anchor: float, anchor_months: float) -> float:
    """q_beta(tau), capped at 1."""
    tau = _finite(delay_months, "delay_months")
    beta = _finite(beta_per_year, "beta_per_year")
    anchor = _finite(anchor_months, "anchor_months")
    q0 = _fraction(q_anchor, "q_anchor")
    if tau < 0 or anchor < 0:
        raise ValueError("delays must be non-negative")
    if beta < 0:
        raise ValueError("beta_per_year must be non-negative")
    if q0 == 0.0:
        return 0.0
    exponent = -beta * (tau - anchor) / 12.0
    return 1.0 if exponent >= math.log(1.0 / q0) else q0 * math.exp(exponent)


def dependence_stress(scenario: Scenario, betas_per_year: list[float], delays_months: list[int],
                      anchor_months: int | None = None) -> pd.DataFrame:
    """Private and ratepayer CoDE when q depends on the delay.

    The anchor is the scenario's delay unless given; q_anchor is the scenario's q.
    Two ratepayer differentials are reported for each delay:

    - ``ratepayer_delay_usd``: level at tau minus the on-time level evaluated at
      q_beta(0), so on-time service is also credited with avoiding delay-induced attrition;
    - ``ratepayer_delay_fixed_q_usd``: level at tau minus the on-time level evaluated at
      q_anchor, which holds the on-time path at the anchor probability and isolates timing.
    """
    anchor = scenario.delay_months if anchor_months is None else _months(anchor_months, "anchor_months")
    q_anchor = scenario.private.realization_probability
    rows = []
    on_time_anchor = ratepayer_cost(scenario, 0)["total"]
    for beta in betas_per_year:
        q_on_time = realization_curve(0, beta, q_anchor, anchor)
        on_time = ratepayer_cost(scenario.with_realization(q_on_time), 0)["total"]
        for tau in delays_months:
            q_tau = realization_curve(tau, beta, q_anchor, anchor)
            s = scenario.with_realization(q_tau).with_delay(_months(tau, "delay_months"))
            priv = private_cost(s)
            rate = ratepayer_cost(s)
            dec = realization_decomposition(s)
            rows.append({"beta_per_year": beta, "delay_months": tau, "realization_probability": q_tau,
                         "private_usd": priv["total"], "lost_margin_usd": priv["lost_margin"],
                         "carrying_usd": priv["carrying"], "elasticity_q": dec["elasticity"],
                         "ratepayer_level_usd": rate["total"],
                         "ratepayer_delay_usd": rate["total"] - on_time,
                         "ratepayer_delay_fixed_q_usd": rate["total"] - on_time_anchor})
    return pd.DataFrame(rows)
