"""Eqs. (1)-(10) against hand calculations."""

import math
from dataclasses import replace

import pytest

from code_delay import (avoided_cost, code_vector, delay_cost_intensity, deployment_fraction, discount_factor,
                        distributionally_acceptable, emissions_social_cost, net_benefit, private_cost, private_monthly,
                        ratepayer_cost, ratepayer_delay_cost, realization_decomposition, social_cost,
                        staged_private_cost)
from code_delay.parameters import RatepayerInputs


def d(t, r):
    return (1 + r) ** (-t / 12)


def test_discount_factor():
    assert discount_factor(0, 0.09) == 1.0
    assert discount_factor(12, 0.09) == pytest.approx(1 / 1.09)
    assert discount_factor(9, 0.0) == 1.0
    with pytest.raises(ValueError):
        discount_factor(-1, 0.09)
    with pytest.raises(ValueError):
        discount_factor(1, -1.0)


@pytest.mark.parametrize("profile,expected", [
    ("static", [0.8, 0.8, 0.8, 0.8]),
    ("linear", [0.2, 0.4, 0.6, 0.8]),
    ("front_loaded", [0.4, 0.8, 0.8, 0.8]),
    ("back_loaded", [0.05, 0.2, 0.45, 0.8]),
])
def test_deployment_profiles(profile, expected):
    got = [deployment_fraction(t, 4, profile, 0.8) for t in range(1, 5)]
    assert got == pytest.approx(expected)
    assert deployment_fraction(9, 4, profile, 0.8) == pytest.approx(expected[-1])   # x_t capped at 1
    assert deployment_fraction(1, 0, profile, 0.8) == 0.0
    with pytest.raises(ValueError):
        deployment_fraction(1, 4, "unknown", 0.8)


def test_private_cost_eq2_by_hand(small):
    r, p = 0.09, 10.0
    margin = 0.6 * 0.7 * 1000 * 0.45
    alpha = [0.8 / 3, 1.6 / 3, 0.8]
    carry = [120_000 * 0.6 * a * 0.09 / 12 for a in alpha]
    expected = sum(d(t, r) * p * (margin + 7.0 + 3.0 + carry[t - 1]) for t in (1, 2, 3))
    got = private_cost(small)
    assert got["total"] == pytest.approx(expected, rel=1e-12)
    assert got["lost_margin"] == pytest.approx(sum(d(t, r) * p * margin for t in (1, 2, 3)))
    assert got["contract_penalty"] == pytest.approx(sum(d(t, r) * p * 7.0 for t in (1, 2, 3)))
    assert got["mitigation_premium"] == pytest.approx(sum(d(t, r) * p * 3.0 for t in (1, 2, 3)))
    assert got["carrying"] == pytest.approx(sum(d(t, r) * p * carry[t - 1] for t in (1, 2, 3)))


def test_only_margin_carries_the_q_weight(small):
    base = private_cost(small)
    half = private_cost(small.with_realization(0.3))
    assert half["lost_margin"] == pytest.approx(base["lost_margin"] / 2)
    for k in ("carrying", "contract_penalty", "mitigation_premium"):
        assert half[k] == pytest.approx(base[k])


def test_private_monthly_matches_total(small, scenario):
    for s in (small, scenario):
        table = private_monthly(s)
        assert len(table) == s.delay_months
        assert table["pv_total"].sum() == pytest.approx(private_cost(s)["total"], rel=1e-12)


def test_private_cost_zero_delay_and_linear_in_capacity(scenario):
    assert private_cost(scenario.with_delay(0))["total"] == 0.0
    assert private_cost(scenario.with_capacity(400.0))["total"] == pytest.approx(2 * private_cost(scenario)["total"])


def test_ratepayer_cost_eq3_by_hand(small):
    r, pg = 0.09, 12.0
    phi_u, phi_s = 0.85, 0.4 + 0.6 * 0.15
    carry = sum(d(t, r) for t in (1, 2, 3)) * pg * 50_000 * 0.06 * 0.45 * phi_u / 12
    strand = d(3, r) * pg * 50_000 * 0.45 * phi_u * phi_s
    got = ratepayer_cost(small)
    assert got["carrying"] == pytest.approx(carry)
    assert got["stranding"] == pytest.approx(strand)
    assert (got["financing_probability"], got["stranding_probability"]) == pytest.approx((phi_u, phi_s))


def test_ratepayer_stock_and_differential(small):
    stock = ratepayer_cost(small, 0)
    assert stock["carrying"] == 0.0
    assert stock["total"] == pytest.approx(12.0 * 50_000 * 0.45 * 0.85 * (0.4 + 0.6 * 0.15))
    assert ratepayer_delay_cost(small, 0) == pytest.approx(0.0)
    assert ratepayer_delay_cost(small) == pytest.approx(ratepayer_cost(small)["total"] - stock["total"])


def test_financing_rules(small):
    linked = replace(small, ratepayer=RatepayerInputs(50_000.0, 0.06, 0.45, "realization_linked",
                                                      abandonment_probability=0.15))
    assert linked.event_probabilities == pytest.approx((0.6, 0.15))
    explicit = replace(small, ratepayer=RatepayerInputs(50_000.0, 0.06, 0.45, "explicit", financing_probability=0.7,
                                                        stranding_probability=0.15))
    assert explicit.event_probabilities == pytest.approx((0.7, 0.15))
    with pytest.raises(ValueError):
        RatepayerInputs(50_000.0, 0.06, 0.45, "milestone", financing_probability=0.85)
    with pytest.raises(ValueError):
        RatepayerInputs(50_000.0, 0.06, 0.45, "realization_linked", abandonment_probability=0.15,
                        financing_probability=0.85)


def test_milestone_level_rises_as_q_falls(scenario):
    assert ratepayer_cost(scenario.with_realization(0.55))["total"] > ratepayer_cost(scenario)["total"]


def test_code_vector_has_no_total(scenario):
    vec = code_vector(scenario, social_usd=5.0)
    assert set(vec.as_dict()) == {"private_usd", "ratepayer_usd", "social_usd"}
    assert vec.private == pytest.approx(private_cost(scenario)["total"])
    assert vec.ratepayer == pytest.approx(ratepayer_cost(scenario)["total"])
    assert vec.social == 5.0


def test_social_cost_eq4_and_eq5():
    r = 0.07
    em, rel, loc = [1.0, 2.0], [0.5, 0.5], 1.0
    expected = 0.7 * sum(d(t, r) * (em[t - 1] + rel[t - 1] + loc) for t in (1, 2))
    assert social_cost(0.7, r, 2, em, rel, loc) == pytest.approx(expected)
    assert social_cost(0.7, r, 2, em, rel, loc, discount=False) == pytest.approx(0.7 * (3.0 + 1.0 + 2.0))
    got = emissions_social_cost(0.5, r, 2, 100.0, 0.5, 0.4, 200.0)
    assert got == pytest.approx(0.5 * sum(d(t, r) * 100 * 0.1 * 200 for t in (1, 2)))
    assert emissions_social_cost(0.5, r, 2, 100.0, 0.3, 0.4, 200.0) < 0      # avoided damage kept, not clipped
    with pytest.raises(ValueError):
        social_cost(0.5, r, 3, [1.0, 2.0])
    with pytest.raises(ValueError):
        social_cost(1.5, r, 2)


def test_dci_eq6(scenario):
    dci = delay_cost_intensity(scenario)
    p_it, pg, tau = 200.0, 260.0, 30
    assert dci["private_usd_per_mw_it_month"] == pytest.approx(private_cost(scenario)["total"] / (p_it * tau))
    assert dci["ratepayer_usd_per_grid_mw_month"] == pytest.approx(ratepayer_delay_cost(scenario) / (pg * tau))
    big = delay_cost_intensity(scenario.with_capacity(600.0))
    assert big["private_usd_per_mw_it_month"] == pytest.approx(dci["private_usd_per_mw_it_month"])
    assert math.isnan(delay_cost_intensity(scenario.with_delay(0))["private_usd_per_mw_it_month"])


def test_static_private_dci_declines_with_delay_only_through_discounting(scenario):
    static = replace(scenario, private=replace(scenario.private, deployment_profile="static"))
    values = [delay_cost_intensity(static.with_delay(t))["private_usd_per_mw_it_month"] for t in (9, 18, 30, 48)]
    assert values == sorted(values, reverse=True)
    flat = replace(static, discount_rate_annual=0.0)
    flat_values = [delay_cost_intensity(flat.with_delay(t))["private_usd_per_mw_it_month"] for t in (9, 48)]
    assert flat_values[0] == pytest.approx(flat_values[1])


def test_avoided_cost_eq7(scenario):
    av = avoided_cost(scenario, 18)
    assert av.beap == av.private
    assert av.private == pytest.approx(private_cost(scenario)["total"] - private_cost(scenario, 18)["total"])
    # the tau = 0 stock cancels: the ratepayer term equals the difference of delay differentials
    assert av.ratepayer == pytest.approx(ratepayer_delay_cost(scenario) - ratepayer_delay_cost(scenario, 18))
    assert avoided_cost(scenario, scenario.delay_months).private == pytest.approx(0.0)
    with pytest.raises(ValueError):
        avoided_cost(scenario, scenario.delay_months + 1)


def test_net_benefit_eq8():
    nb = net_benefit(100.0, 10.0, 60.0, 30.0)
    assert nb.value == pytest.approx(20.0)
    assert nb.potentially_welfare_improving and nb.privately_worthwhile
    assert nb.implementation_cost_bound == pytest.approx(80.0)
    assert net_benefit(100.0, 10.0, 80.0, 30.0).value == pytest.approx(0.0)      # zero at the bound
    assert not net_benefit(100.0, 10.0, 80.0, 30.0).potentially_welfare_improving     # strict inequality
    assert not net_benefit(50.0, 0.0, 60.0, 0.0).privately_worthwhile
    assert distributionally_acceptable(90.0, 60.0, 30.0)
    assert not distributionally_acceptable(89.0, 60.0, 30.0)


def test_staged_eq9(scenario):
    tau0 = scenario.delay_months
    base = private_cost(scenario)["total"]
    assert staged_private_cost(scenario, 9, 0.0)["staged"] == pytest.approx(base)
    assert staged_private_cost(scenario, tau0, 1.0)["staged"] == pytest.approx(base)
    full = staged_private_cost(scenario, 9, 1.0)
    assert full["staged"] == pytest.approx(private_cost(scenario, 9)["total"])
    half = staged_private_cost(scenario, 9, 0.6)
    p = scenario.project.it_capacity_mw
    assert half["staged"] == pytest.approx(private_cost(scenario, 9, 0.6 * p)["total"]
                                           + private_cost(scenario, tau0, 0.4 * p)["total"])
    assert half["value_of_partial_service"] == pytest.approx(base - half["staged"])
    custom = staged_private_cost(scenario, 9, 0.6, revenue_equivalent=lambda f: f ** 2)
    assert custom["revenue_equivalent_fraction"] == pytest.approx(0.36)
    assert custom["value_of_partial_service"] < half["value_of_partial_service"]
    with pytest.raises(ValueError):
        staged_private_cost(scenario, tau0 + 1, 0.6)
    with pytest.raises(ValueError):
        staged_private_cost(scenario, 9, 1.5)


def test_decomposition_eq10(scenario, small):
    for s in (scenario, small):
        dec = realization_decomposition(s)
        assert dec["q"] * dec["A"] + dec["B"] + dec["Pi"] == pytest.approx(private_cost(s)["total"])
        assert 0.0 < dec["elasticity"] < 1.0
    dec = realization_decomposition(scenario)
    assert dec["Pi"] == 0.0
    assert dec["elasticity"] == pytest.approx(dec["q"] * dec["A"] / (dec["q"] * dec["A"] + dec["B"]))
    # numerical elasticity d ln C / d ln q
    q, h = scenario.private.realization_probability, 1e-6
    c1 = private_cost(scenario.with_realization(q * (1 + h)))["total"]
    c0 = private_cost(scenario.with_realization(q * (1 - h)))["total"]
    assert (math.log(c1) - math.log(c0)) / (math.log(1 + h) - math.log(1 - h)) == pytest.approx(dec["elasticity"], rel=1e-6)
    zero_q = realization_decomposition(scenario.with_realization(0.0))
    assert zero_q["elasticity"] == 0.0 and zero_q["A"] > 0


def test_capacity_and_month_validation(scenario):
    for bad in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            private_cost(scenario, it_capacity_mw=bad)
        with pytest.raises(ValueError):
            private_monthly(scenario, it_capacity_mw=bad)
    for bad in (float("inf"), float("nan"), 2.5, -1, True):
        with pytest.raises(ValueError):
            private_cost(scenario, delay_months=bad)
    with pytest.raises(ValueError):
        deployment_fraction(1, 4, "static", 1.5)
