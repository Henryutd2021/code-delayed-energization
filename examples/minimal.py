"""One delayed-energization scenario: the CoDE vector, its components and the DCI.

Illustrative inputs (code_delay.illustrative): the numbers say nothing about any real project.
Run: python examples/minimal.py
"""

from code_delay import (code_vector, delay_cost_intensity, illustrative_scenario, private_cost, ratepayer_cost,
                        ratepayer_delay_cost, realization_decomposition)

M = 1e6
s = illustrative_scenario()
print(f"Request: {s.project.it_capacity_mw:.0f} MW-IT -> {s.project.grid_mw:.0f} grid MW, "
      f"{s.project.interconnection_mva:.0f} MVA; delay {s.delay_months} months")

vec = code_vector(s)
print(f"CoDE vector (MUSD, not added): private {vec.private / M:.1f}, ratepayer {vec.ratepayer / M:.1f}, "
      f"social {vec.social / M:.1f} (no pathway)")

priv = private_cost(s)
print("Private components (MUSD): " + ", ".join(f"{k} {v / M:.1f}" for k, v in priv.items() if k != "total"))

rate = ratepayer_cost(s)
print(f"Ratepayer (MUSD): carrying {rate['carrying'] / M:.1f}, stranding {rate['stranding'] / M:.1f}; "
      f"delay-attributable {ratepayer_delay_cost(s) / M:.1f} (phi_u {rate['financing_probability']:.2f}, "
      f"phi_s {rate['stranding_probability']:.2f})")

dci = delay_cost_intensity(s)
print(f"DCI: private {dci['private_usd_per_mw_it_month'] / 1e3:.1f} kUSD per MW-IT-month, "
      f"ratepayer {dci['ratepayer_usd_per_grid_mw_month'] / 1e3:.2f} kUSD per grid-MW-month")

dec = realization_decomposition(s)
print(f"Eq. (10): q*A {dec['q'] * dec['A'] / M:.1f}, B {dec['B'] / M:.1f} MUSD; elasticity wrt q {dec['elasticity']:.3f}")
