import pytest

from code_delay import illustrative_scenario
from code_delay.parameters import PrivateInputs, Project, RatepayerInputs, Scenario


@pytest.fixture
def scenario():
    return illustrative_scenario()


@pytest.fixture
def small():
    """A short case for hand calculations: 3 months, every private term non-zero."""
    return Scenario(
        name="small", delay_months=3, discount_rate_annual=0.09,
        project=Project(it_capacity_mw=10.0, pue=1.2, power_factor=0.8),
        private=PrivateInputs(gross_value_usd_per_mw_it_month=1000.0, operating_margin=0.45,
                              realization_probability=0.6, substitution_fraction=0.3,
                              committed_capital_usd_per_mw_it=120_000.0, committed_capital_fraction=0.6,
                              deployment_peak=0.8, carrying_rate_annual=0.09, deployment_profile="linear",
                              contract_penalty_usd_per_mw_it_month=7.0, mitigation_premium_usd_per_mw_it_month=3.0),
        ratepayer=RatepayerInputs(upgrade_cost_usd_per_grid_mw=50_000.0, utility_carrying_rate_annual=0.06,
                                  residual_share=0.45, financing_rule="milestone", financing_probability=0.85,
                                  abandonment_probability=0.15),
    )
