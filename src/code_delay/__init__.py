"""CoDE framework: the Cost of Delayed Grid Energization for large loads such as AI data centers.

Present-value accounting of a delay before first usable grid service, kept separately
for the developer (private), the utility and its ratepayers, and society, with delay cost
intensity, the break-even acceleration payment and a net-benefit test. Equation numbers
refer to the article cited in README.md; the mathematics is in docs/formulation.md.
"""

from .accounting import (AvoidedCost, CodeVector, NetBenefit, avoided_cost, code_vector, delay_cost_intensity,
                         deployment_fraction, discount_factor, distributionally_acceptable, emissions_social_cost,
                         net_benefit, private_cost, private_monthly, ratepayer_cost, ratepayer_delay_cost,
                         realization_decomposition, social_cost, staged_private_cost)
from .dependence import dependence_stress, realization_curve
from .illustrative import illustrative_bridge, illustrative_scenario
from .io import read_scenario, scenario_from_dict, scenario_to_dict, write_scenario, write_table
from .parameters import (PrivateInputs, Project, RatepayerInputs, Scenario, get_parameter, set_parameter,
                         set_parameters, usd_per_kw_month_to_usd_per_mw_month)
from .pathways import BridgeInputs, acceleration_options, bridge_pathway, lb_per_kwh_to_t_per_mwh
from .sweeps import (evaluate, full_factorial, latin_hypercube, percentiles_by, rank_correlations,
                     sample_scenarios, tariff_cases)

__version__ = "1.0.2"

__all__ = [
    "AvoidedCost", "BridgeInputs", "CodeVector", "NetBenefit", "PrivateInputs", "Project", "RatepayerInputs",
    "Scenario", "acceleration_options", "avoided_cost", "bridge_pathway", "code_vector", "delay_cost_intensity",
    "dependence_stress", "deployment_fraction", "discount_factor", "distributionally_acceptable",
    "emissions_social_cost", "evaluate", "full_factorial", "get_parameter", "illustrative_bridge",
    "illustrative_scenario", "latin_hypercube", "lb_per_kwh_to_t_per_mwh", "net_benefit", "percentiles_by",
    "private_cost", "private_monthly", "rank_correlations", "ratepayer_cost", "ratepayer_delay_cost",
    "read_scenario", "realization_curve", "realization_decomposition", "sample_scenarios", "scenario_from_dict",
    "scenario_to_dict", "set_parameter", "set_parameters", "social_cost", "staged_private_cost", "tariff_cases",
    "usd_per_kw_month_to_usd_per_mw_month", "write_scenario", "write_table",
]
