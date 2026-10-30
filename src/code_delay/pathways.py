"""Acceleration options and priced pathways evaluated with Eqs. (5), (7) and (8).

- :func:`bridge_pathway`: temporary supply (for example natural-gas bridge power) serves
  the load during the first ``bridge_months`` of the delay. It avoids the private cost of
  those months, leaves the network upgrade schedule (and so the ratepayer account)
  unchanged, and adds the emissions externality of Eq. (5) against on-time grid service.
- :func:`acceleration_options`: options that shorten the delay or stage service, with
  their BEAP (Eq. 7) and avoided ratepayer cost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .accounting import (avoided_cost, emissions_social_cost, net_benefit, private_monthly, ratepayer_cost,
                         staged_private_cost)
from .parameters import Scenario, _fraction, _months, _non_negative

HOURS_PER_MONTH = 730.0          # 8,760 h / 12
LB_PER_TONNE = 2204.6226218487757


def lb_per_kwh_to_t_per_mwh(value: float) -> float:
    """Convert an emission factor in lb CO2/kWh to t CO2/MWh."""
    return _non_negative(value, "value") * 1000.0 / LB_PER_TONNE


@dataclass(frozen=True)
class BridgeInputs:
    """A temporary-supply pathway that serves the whole delayed load in its months.

    The wrapper :func:`bridge_pathway` applies when every realized project uses the
    bridge, so the pathway probability equals the realization probability (p_h = q), and
    the bridge supplies the facility's load, so the service earns the private value of
    those months. Leave ``pathway_probability`` unset to take q from the scenario. For
    another pathway probability, price the emissions with
    :func:`code_delay.emissions_social_cost` and the private side separately.
    """

    bridge_months: int                       # months served by the bridge, counted from month 1
    utilization: float                       # load factor of the facility's grid MW while bridged, in (0, 1]
    bridge_t_per_mwh: float                  # eps_h, direct emission factor of the bridge
    counterfactual_t_per_mwh: float          # eps_0, factor of on-time grid service
    pathway_probability: float | None = None # p_h; None means p_h = q of the scenario
    discount_damages: bool = True            # d_t in Eq. (5); False sets d_t = 1
    dollar_factor: float = 1.0               # converts the social-cost dollar year to the analysis year

    def __post_init__(self) -> None:
        if _months(self.bridge_months, "bridge_months") == 0:
            raise ValueError("bridge_months must be at least 1")
        if _fraction(self.utilization, "utilization") == 0:
            raise ValueError("utilization must be positive: the bridge must serve the load")
        _non_negative(self.bridge_t_per_mwh, "bridge_t_per_mwh")
        _non_negative(self.counterfactual_t_per_mwh, "counterfactual_t_per_mwh")
        if self.pathway_probability is not None:
            _fraction(self.pathway_probability, "pathway_probability")
        if not isinstance(self.discount_damages, bool):
            raise ValueError("discount_damages must be True or False")
        if _non_negative(self.dollar_factor, "dollar_factor") == 0:
            raise ValueError("dollar_factor must be positive")


def bridge_pathway(scenario: Scenario, bridge: BridgeInputs, social_cost_usd_per_t: list[float] | float) -> pd.DataFrame:
    """Evaluate a bridge pathway for one or more social costs of CO2 (USD/t).

    One row per social-cost value: bridged energy, conditional and ex-ante incremental
    emissions, Delta C^soc (Eq. 5), avoided private cost (BEAP of the bridge), avoided
    ratepayer cost (zero: the upgrade schedule does not change), and the strict upper
    bound on the implementation cost C^add for Eq. (8) to hold, in total and per MWh bridged.
    """
    b = bridge.bridge_months
    if b > scenario.delay_months:
        raise ValueError("bridge_months cannot exceed the delay")
    q = scenario.private.realization_probability
    p_h = q if bridge.pathway_probability is None else bridge.pathway_probability
    if not math.isclose(p_h, q, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("bridge_pathway assumes every realized project uses the bridge (p_h = q); "
                         "use emissions_social_cost for another pathway probability")
    values = [social_cost_usd_per_t] if isinstance(social_cost_usd_per_t, (int, float)) else list(social_cost_usd_per_t)
    energy_per_month = scenario.project.grid_mw * bridge.utilization * HOURS_PER_MONTH
    energy = energy_per_month * b
    diff = bridge.bridge_t_per_mwh - bridge.counterfactual_t_per_mwh
    monthly = private_monthly(scenario)
    avoided_private = float(monthly.loc[monthly["month"] <= b, "pv_total"].sum())
    rows = []
    for v in values:
        v = _non_negative(v, "social_cost_usd_per_t")
        damage = emissions_social_cost(p_h, scenario.discount_rate_annual, b, energy_per_month,
                                       bridge.bridge_t_per_mwh, bridge.counterfactual_t_per_mwh, v,
                                       discount=bridge.discount_damages) * bridge.dollar_factor
        nb = net_benefit(avoided_private, 0.0, 0.0, damage)
        rows.append({"social_cost_usd_per_t": v, "bridge_months": b, "pathway_probability": p_h,
                     "bridged_energy_mwh": energy, "conditional_incremental_t": energy * diff,
                     "ex_ante_incremental_t": energy * diff * p_h,
                     "added_social_usd": damage, "avoided_private_usd": avoided_private,
                     "avoided_ratepayer_usd": 0.0, "implementation_cost_bound_usd": nb.implementation_cost_bound,
                     "implementation_cost_bound_usd_per_mwh": (nb.implementation_cost_bound / energy
                                                               if energy > 0 else math.nan)})
    return pd.DataFrame(rows)


def acceleration_options(scenario: Scenario, shortened_delays: list[int] | None = None,
                         staged: list[tuple[int, float]] | None = None) -> pd.DataFrame:
    """BEAP and avoided ratepayer cost for delay reductions and staged service.

    ``shortened_delays``: new delays tau_1 (full service earlier).
    ``staged``: (first-service month tau_e, served fraction f) pairs; the unserved part
    waits until tau_0. For staged service the ratepayer differential follows the
    same split: the served share of the request is evaluated at tau_e.
    """
    rows = []
    rate0 = ratepayer_cost(scenario)["total"]
    for tau1 in shortened_delays or []:
        av = avoided_cost(scenario, tau1)
        rows.append({"option": f"full service at month {tau1}", "first_service_months": tau1, "served_fraction": 1.0,
                     "beap_usd": av.beap, "avoided_ratepayer_usd": av.ratepayer})
    for tau_e, f in staged or []:
        st = staged_private_cost(scenario, tau_e, f)
        g = st["revenue_equivalent_fraction"]
        rate_staged = g * ratepayer_cost(scenario, tau_e)["total"] + (1.0 - g) * rate0
        rows.append({"option": f"{f:.0%} served at month {tau_e}", "first_service_months": tau_e,
                     "served_fraction": f, "beap_usd": st["value_of_partial_service"],
                     "avoided_ratepayer_usd": rate0 - rate_staged})
    return pd.DataFrame(rows, columns=["option", "first_service_months", "served_fraction", "beap_usd",
                                       "avoided_ratepayer_usd"])
