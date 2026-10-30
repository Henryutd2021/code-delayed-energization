"""Acceleration options on illustrative inputs: full and staged service, a bridge pathway, the net-benefit test.

Illustrative inputs (code_delay.illustrative): the numbers say nothing about any real project.
Run: python examples/options.py
"""

from code_delay import (acceleration_options, bridge_pathway, distributionally_acceptable, illustrative_bridge,
                        illustrative_scenario, net_benefit)
from code_delay.illustrative import (ILLUSTRATIVE_SHORTENED_DELAYS, ILLUSTRATIVE_SOCIAL_COSTS_USD_PER_T,
                                     ILLUSTRATIVE_STAGED)

M = 1e6
s = illustrative_scenario()

opts = acceleration_options(s, shortened_delays=ILLUSTRATIVE_SHORTENED_DELAYS, staged=ILLUSTRATIVE_STAGED)
print("Gross private value (BEAP) and avoided ratepayer cost, before implementation cost and risk (MUSD):")
print(opts.assign(beap_usd=(opts.beap_usd / M).round(1),
                  avoided_ratepayer_usd=(opts.avoided_ratepayer_usd / M).round(1)).to_string(index=False))

bridge = illustrative_bridge()
br = bridge_pathway(s, bridge, ILLUSTRATIVE_SOCIAL_COSTS_USD_PER_T)
print(f"\nBridge for the first {bridge.bridge_months} months: {br.bridged_energy_mwh[0] / 1e3:.0f} GWh, "
      f"ex-ante incremental emissions {br.ex_ante_incremental_t[0] / 1e3:.1f} kt CO2")
print("Strict upper bound on the bridge's implementation cost C^add for Eq. (8) to hold:")
cols = ["social_cost_usd_per_t", "added_social_usd", "avoided_private_usd", "implementation_cost_bound_usd",
        "implementation_cost_bound_usd_per_mwh"]
print(br[cols].assign(added_social_usd=br.added_social_usd / M, avoided_private_usd=br.avoided_private_usd / M,
                      implementation_cost_bound_usd=br.implementation_cost_bound_usd / M).round(1).to_string(index=False))

row = br.iloc[1]
premium = 0.5 * row.implementation_cost_bound_usd        # an illustrative power-cost premium C^add
nb = net_benefit(row.avoided_private_usd, row.avoided_ratepayer_usd, premium, row.added_social_usd)
print(f"\nNet-benefit test at C^add = {premium / M:.1f} MUSD: value {nb.value / M:.1f} MUSD, "
      f"potentially welfare-improving {nb.potentially_welfare_improving}, privately worthwhile {nb.privately_worthwhile}")
print("Distributionally acceptable if the developer pays C^add only:",
      distributionally_acceptable(premium, premium, row.added_social_usd))
print("... and if it also compensates the added externality:",
      distributionally_acceptable(premium + row.added_social_usd, premium, row.added_social_usd))
