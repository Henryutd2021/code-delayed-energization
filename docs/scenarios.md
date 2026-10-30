# Study design

How the article organizes its case study, and how to set up each part with this package. The article's values are in its Table II and Section III; they are not repeated here. All benchmark values in such a study are illustrative: ranges are assumed, cases are unweighted, no joint distribution is estimated, and results are sensitivity ranges rather than forecasts.

## Contents

1. [Base case](#base-case)
2. [Full-factorial lattice](#full-factorial-lattice)
3. [Latin hypercube screening](#latin-hypercube-screening)
4. [Delay–realization dependence](#delayrealization-dependence)
5. [Staged service](#staged-service)
6. [Tariff stress](#tariff-stress)
7. [Bridge power as a priced pathway](#bridge-power-as-a-priced-pathway)
8. [Reading the results](#reading-the-results)

## Base case

One project, one delay, one value per parameter; contract and mitigation terms set to zero unless project data exist. Report the CoDE vector (Eq. 1) without a total, the decomposition of each perspective, the ratepayer level split into the delay differential and the $`\tau = 0`$ stock, and both DCIs (Eq. 6).

```python
from code_delay import read_scenario, code_vector, private_cost, ratepayer_cost, ratepayer_delay_cost, delay_cost_intensity
s = read_scenario("scenario.json")
code_vector(s); private_cost(s); ratepayer_cost(s); ratepayer_delay_cost(s); delay_cost_intensity(s)
```

## Full-factorial lattice

The article varies ten dimensions jointly: capacity, delay, $`V`$, $`\mu`$, $`r`$, $`s`$, $`q`$, $`K`$, $`c`$ and the deployment profile. Realization probability and delay vary independently, so percentiles of the set summarize the assumed lattice, not a distribution over projects.

```python
from code_delay import full_factorial, evaluate, percentiles_by
grid = {"project.it_capacity_mw": [...], "delay_months": [...], "private.gross_value_usd_per_mw_it_month": [...],
        "private.operating_margin": [...], "discount_rate_annual": [...], "private.substitution_fraction": [...],
        "private.realization_probability": [...], "private.committed_capital_usd_per_mw_it": [...],
        "private.committed_capital_fraction": [...], "private.deployment_profile": ["static", "linear", "front_loaded", "back_loaded"]}
table = evaluate(full_factorial(s, grid), parameters=list(grid))
percentiles_by(table, "delay_months", "private_usd")
```

Command line: `code-delay sweep scenario.json grid.json --out lattice.csv`.

## Latin hypercube screening

At a fixed capacity and delay, the article samples the continuous ranges (gross value, margin, discount rate, substitution, realization, committed fraction, committed capital cost, deployment peak, PUE, upgrade cost, financing probability, residual share, post-realization stranding probability) and the deployment profile, and reports Spearman rank correlations of the inputs with private and ratepayer CoDE. Correlations scale with the assumed ranges, so they order sensitivity within those ranges only. The screen runs on levels, so the ratepayer correlations include the stranding stock.

```python
from code_delay import sample_scenarios, evaluate, rank_correlations
ranges = {"private.gross_value_usd_per_mw_it_month": (low, high), ...}
cats = {"private.deployment_profile": ["static", "linear", "front_loaded", "back_loaded"]}
table = evaluate(sample_scenarios(s, ranges, n_samples=500, seed=1, categorical=cats), parameters=list(ranges) + list(cats))
rank_correlations(table, list(ranges), ["private_usd", "ratepayer_level_usd"], categorical=list(cats))
```

Command line: `code-delay lhs scenario.json ranges.json --samples 500 --seed 1 --out-dir outputs/lhs`.

## Delay–realization dependence

A stress test replaces the base $`q`$ with $`q_\beta(\tau)`$ (formulation, text relations), for a few values of $`\beta`$, all anchored at the base delay. Private CoDE then follows Eq. (10): the carrying cost, which does not depend on $`q`$, bounds how far realization risk can move it. Under milestone financing the ratepayer level rises as $`q`$ falls (through $`\phi_s`$); under realization-linked financing ($`\phi_u = q`$, $`\phi_s = p_a`$) it falls. Which case applies depends on whether irreversible network commitment precedes or follows project resolution.

```python
from code_delay import dependence_stress
dependence_stress(s, betas_per_year=[0.0, 0.08, 0.15], delays_months=[...])          # anchor = s.delay_months
```

## Staged service

First service at several months $`\tau_e < \tau_0`$ for several fractions $`f`$ (Eq. 9), with $`g(f) = f`$ unless a revenue-equivalence curve is given. The private value of partial service is a gross threshold: it excludes the implementation cost $`C^{\mathrm{add}}_m`$ and risk. Earlier service also brings the stranding write-off forward, so the avoided ratepayer cost is net of that effect.

```python
from code_delay import acceleration_options
acceleration_options(s, shortened_delays=[...], staged=[(tau_e, f), ...])
```

Command line: `code-delay staged scenario.json --first-service 9 18 --fractions 0.3 0.6 1 --out staged.csv`.

## Tariff stress

Vary the residual ratepayer share, the upgrade cost and the post-realization stranding probability, from developer-funded upgrades ($`\rho = 0`$) to full exposure. Private CoDE is unchanged; the ratepayer level is what tariff design allocates, and the differential is what acceleration avoids.

```python
from code_delay import tariff_cases
tariff_cases(s, {"developer_funded": {"ratepayer.residual_share": 0.0}, "base": {}, "high": {...}})
```

## Bridge power as a priced pathway

A temporary supply (for example a natural-gas bridge) is both a mitigation option and a source of externality, so both sides are evaluated against the same on-time counterfactual: the avoided private cost of the bridged months, Eq. (5) for the added emissions at several values of the social cost of CO₂, and the strict upper bound on the power-cost premium $`C^{\mathrm{add}}_m`$ for Eq. (8) to hold. The wrapper assumes that every realized project uses the bridge ($`p_h = q`$).

```python
from code_delay import BridgeInputs, bridge_pathway, lb_per_kwh_to_t_per_mwh
b = BridgeInputs(bridge_months=..., utilization=..., bridge_t_per_mwh=lb_per_kwh_to_t_per_mwh(...),
                 counterfactual_t_per_mwh=lb_per_kwh_to_t_per_mwh(...), dollar_factor=...)      # p_h = q
bridge_pathway(s, b, [low_scc, central_scc, high_scc])
```

The direct-CO₂ term changes sign when the counterfactual factor exceeds the bridge factor. Under milestone financing, a bridge that also raises the realization probability lowers the ratepayer stranding term; `bridge_pathway` does not include that credit, and it can be evaluated separately with `ratepayer_cost` at the higher $`q`$.

## Reading the results

- Keep the three perspectives apart; combine them only through Eq. (8).
- Compare the ratepayer **differential**, not the level, with private CoDE and with BEAP.
- Private DCI does not depend on capacity; it changes with the delay only through discounting and the deployment profile.
- A high BEAP is no evidence of a comparable public benefit: Eq. (8) depends on $`C^{\mathrm{add}}_m`$ and on the pathway externality.
