"""Illustrative inputs for examples and tests.

Round, invented values that show how the framework behaves. They are not a benchmark
for any market, utility or project, and the outputs computed from them say nothing
about real data centers. Replace every value with project, tariff and pathway data
(docs/data_pipeline.md).
"""

from __future__ import annotations

from .parameters import PrivateInputs, Project, RatepayerInputs, Scenario
from .pathways import BridgeInputs


def illustrative_scenario() -> Scenario:
    return Scenario(
        name="illustrative",
        delay_months=30,
        discount_rate_annual=0.07,
        project=Project(it_capacity_mw=200.0, pue=1.3, power_factor=0.9),
        private=PrivateInputs(
            gross_value_usd_per_mw_it_month=180_000.0,
            operating_margin=0.30,
            realization_probability=0.8,
            substitution_fraction=0.2,
            committed_capital_usd_per_mw_it=15_000_000.0,
            committed_capital_fraction=0.8,
            deployment_peak=0.6,
            carrying_rate_annual=0.07,
            deployment_profile="linear",
        ),
        ratepayer=RatepayerInputs(
            upgrade_cost_usd_per_grid_mw=1_500_000.0,
            utility_carrying_rate_annual=0.07,
            residual_share=0.4,
            financing_rule="milestone",
            financing_probability=0.85,
            abandonment_probability=0.15,
        ),
    )


def illustrative_bridge() -> BridgeInputs:
    return BridgeInputs(bridge_months=9, utilization=0.9, bridge_t_per_mwh=0.45, counterfactual_t_per_mwh=0.38,
                        discount_damages=True, dollar_factor=1.0)   # p_h = q of the scenario


ILLUSTRATIVE_SOCIAL_COSTS_USD_PER_T = [100.0, 200.0, 300.0]

ILLUSTRATIVE_GRID = {
    "project.it_capacity_mw": [150.0, 250.0, 400.0],
    "delay_months": [9, 18, 30, 48],
    "private.operating_margin": [0.22, 0.32, 0.42],
    "private.realization_probability": [0.6, 0.8, 1.0],
    "private.deployment_profile": ["static", "linear", "front_loaded", "back_loaded"],
}

ILLUSTRATIVE_RANGES = {
    "private.gross_value_usd_per_mw_it_month": (120_000.0, 240_000.0),
    "private.operating_margin": (0.15, 0.45),
    "private.realization_probability": (0.55, 1.0),
    "private.substitution_fraction": (0.0, 0.4),
    "private.committed_capital_usd_per_mw_it": (8_000_000.0, 30_000_000.0),
    "private.deployment_peak": (0.3, 0.9),
    "discount_rate_annual": (0.05, 0.11),
    "project.pue": (1.1, 1.4),
    "ratepayer.residual_share": (0.0, 1.0),
    "ratepayer.upgrade_cost_usd_per_grid_mw": (800_000.0, 2_500_000.0),
    "ratepayer.abandonment_probability": (0.04, 0.25),
}

ILLUSTRATIVE_SHORTENED_DELAYS = [9, 18]

ILLUSTRATIVE_STAGED = [(9, 0.3), (9, 0.6), (18, 0.6), (18, 0.9)]

ILLUSTRATIVE_CATEGORICAL = {"private.deployment_profile": ["static", "linear", "front_loaded", "back_loaded"]}

ILLUSTRATIVE_TARIFF_CASES = {
    "developer_funded": {"ratepayer.residual_share": 0.0},
    "partial_protection": {"ratepayer.residual_share": 0.3},
    "illustrative": {},
    "costly_upgrade": {"ratepayer.upgrade_cost_usd_per_grid_mw": 2_500_000.0},
    "full_exposure": {"ratepayer.residual_share": 1.0, "ratepayer.abandonment_probability": 0.25},
}
