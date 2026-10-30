"""Bridge pathway, acceleration options and the delay-realization dependence stress."""

import math

import pytest

from code_delay import (BridgeInputs, acceleration_options, bridge_pathway, dependence_stress, illustrative_bridge,
                        lb_per_kwh_to_t_per_mwh, private_cost, private_monthly, ratepayer_cost, realization_curve)


def test_emission_factor_conversion():
    assert lb_per_kwh_to_t_per_mwh(2.2046226218487757) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        lb_per_kwh_to_t_per_mwh(-1.0)


def test_bridge_pathway(scenario):
    b = illustrative_bridge()
    table = bridge_pathway(scenario, b, [100.0, 200.0])
    q = scenario.private.realization_probability
    assert (table["pathway_probability"] == q).all()                          # p_h = q by default
    energy = scenario.project.grid_mw * b.utilization * 730.0 * b.bridge_months
    assert table["bridged_energy_mwh"].iloc[0] == pytest.approx(energy)
    diff = b.bridge_t_per_mwh - b.counterfactual_t_per_mwh
    assert table["ex_ante_incremental_t"].iloc[0] == pytest.approx(energy * diff * q)
    # avoided private cost by hand: Eq. (2) terms of months 1..b, alpha_t in the tau_0 window (linear profile)
    pi, r, tau0, p_it = scenario.private, scenario.discount_rate_annual, scenario.delay_months, 200.0
    by_hand = 0.0
    for t in range(1, b.bridge_months + 1):
        alpha = pi.deployment_peak * t / tau0
        monthly_cost = p_it * (q * (1 - pi.substitution_fraction) * pi.gross_value_usd_per_mw_it_month
                               * pi.operating_margin + pi.committed_capital_usd_per_mw_it
                               * pi.committed_capital_fraction * alpha * pi.carrying_rate_annual / 12)
        by_hand += (1 + r) ** (-t / 12) * monthly_cost
    assert table["avoided_private_usd"].iloc[0] == pytest.approx(by_hand, rel=1e-12)
    assert (table["avoided_ratepayer_usd"] == 0.0).all()
    damage = table["added_social_usd"]
    assert damage.iloc[0] == pytest.approx(q * diff * 100.0 * energy / b.bridge_months
                                           * sum((1 + r) ** (-t / 12) for t in range(1, b.bridge_months + 1)))
    assert damage.iloc[1] == pytest.approx(2 * damage.iloc[0])
    assert table["implementation_cost_bound_usd"].iloc[0] == pytest.approx(by_hand - damage[0])
    assert table["implementation_cost_bound_usd_per_mwh"].iloc[0] == pytest.approx(
        table.implementation_cost_bound_usd[0] / energy)


def test_bridge_zero_capacity(scenario):
    row = bridge_pathway(scenario.with_capacity(0.0), illustrative_bridge(), 100.0).iloc[0]
    assert row.bridged_energy_mwh == 0.0 and row.avoided_private_usd == 0.0 and row.added_social_usd == 0.0
    assert math.isnan(row.implementation_cost_bound_usd_per_mwh)


def test_bridge_applicability(scenario):
    q = scenario.private.realization_probability
    assert len(bridge_pathway(scenario, BridgeInputs(9, 0.9, 0.45, 0.38, pathway_probability=q), 100.0)) == 1
    with pytest.raises(ValueError, match="p_h = q"):
        bridge_pathway(scenario, BridgeInputs(9, 0.9, 0.45, 0.38, pathway_probability=0.0), 100.0)
    with pytest.raises(ValueError, match="utilization"):
        BridgeInputs(9, 0.0, 0.45, 0.38)
    with pytest.raises(ValueError, match="bridge_months"):
        BridgeInputs(0, 0.9, 0.45, 0.38)


def test_bridge_damage_options(scenario):
    undiscounted = BridgeInputs(9, 0.9, 0.45, 0.38, discount_damages=False, dollar_factor=1.3)
    row = bridge_pathway(scenario, undiscounted, 100.0).iloc[0]
    assert row.added_social_usd == pytest.approx(row.bridged_energy_mwh * 0.07 * 100 * 0.8 * 1.3)
    cleaner = BridgeInputs(9, 0.9, 0.30, 0.38)
    assert bridge_pathway(scenario, cleaner, 100.0).added_social_usd.iloc[0] < 0      # sign change kept
    with pytest.raises(ValueError):
        bridge_pathway(scenario, BridgeInputs(scenario.delay_months + 1, 0.9, 0.45, 0.38), 100.0)
    with pytest.raises(ValueError):
        BridgeInputs(9, 1.2, 0.45, 0.38)


def test_acceleration_options(scenario):
    opts = acceleration_options(scenario, shortened_delays=[18], staged=[(18, 1.0), (18, 0.6), (9, 0.0)])
    full, staged_full, half, none = opts.to_dict("records")
    assert full["beap_usd"] == pytest.approx(staged_full["beap_usd"])
    assert full["avoided_ratepayer_usd"] == pytest.approx(staged_full["avoided_ratepayer_usd"])
    assert full["beap_usd"] == pytest.approx(private_cost(scenario)["total"] - private_cost(scenario, 18)["total"])
    assert half["beap_usd"] == pytest.approx(0.6 * full["beap_usd"])
    assert half["avoided_ratepayer_usd"] == pytest.approx(0.6 * full["avoided_ratepayer_usd"])
    assert none["beap_usd"] == pytest.approx(0.0) and none["avoided_ratepayer_usd"] == pytest.approx(0.0)
    assert list(acceleration_options(scenario).columns) == ["option", "first_service_months", "served_fraction",
                                                            "beap_usd", "avoided_ratepayer_usd"]


def test_realization_curve():
    assert realization_curve(30, 0.12, 0.7, 30) == pytest.approx(0.7)
    assert realization_curve(54, 0.0, 0.7, 30) == pytest.approx(0.7)
    assert realization_curve(54, 0.12, 0.7, 30) == pytest.approx(0.7 * math.exp(-0.24))
    assert realization_curve(0, 0.5, 0.7, 30) == 1.0                          # capped
    values = [realization_curve(t, 0.12, 0.7, 30) for t in (9, 18, 30, 42, 54)]
    assert values == sorted(values, reverse=True)
    assert realization_curve(15, 0.12, 0.0, 30) == 0.0
    with pytest.raises(ValueError):
        realization_curve(15, -0.1, 0.7, 30)


def test_dependence_stress(scenario):
    table = dependence_stress(scenario, [0.0, 0.15], [15, 30, 48])
    assert len(table) == 6
    anchor = table[table.delay_months == scenario.delay_months]
    assert anchor.realization_probability.tolist() == pytest.approx([0.8, 0.8])
    assert anchor.private_usd.nunique() == 1
    const = table[table.beta_per_year == 0.0]
    assert (const.ratepayer_delay_usd - const.ratepayer_delay_fixed_q_usd).abs().max() == pytest.approx(0.0, abs=1e-6)
    strong = table[(table.beta_per_year == 0.15) & (table.delay_months == 48)].iloc[0]
    q48 = realization_curve(48, 0.15, 0.8, 30)
    s48 = scenario.with_realization(q48).with_delay(48)
    assert strong.private_usd == pytest.approx(private_cost(s48)["total"])
    q0 = realization_curve(0, 0.15, 0.8, 30)
    on_time = ratepayer_cost(scenario.with_realization(q0), 0)["total"]
    assert strong.ratepayer_delay_usd == pytest.approx(ratepayer_cost(s48)["total"] - on_time)
    assert strong.ratepayer_delay_fixed_q_usd == pytest.approx(ratepayer_cost(s48)["total"]
                                                               - ratepayer_cost(scenario, 0)["total"])
    custom = dependence_stress(scenario, [0.15], [15], anchor_months=15)
    assert custom.realization_probability.iloc[0] == pytest.approx(0.8)
