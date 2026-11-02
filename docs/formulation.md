# Formulation

The Cost of Delayed Grid Energization (CoDE) as stated in the article (Li and She, NAPS 2026; see the README).

- Equation numbers (1)–(10) follow the article, so that each part can be matched to it.
- Relations that the article states in the text, without a number, are collected in [Relations stated in the text](#relations-stated-in-the-text).
- [Conventions of this implementation](#conventions-of-this-implementation) lists the definitions that the framework makes explicit.
- The last column of each table names the code that implements the symbol or equation (package `code_delay`).

## Contents

1. [Symbols](#symbols)
2. [The CoDE vector, Eq. (1)](#the-code-vector)
3. [Private perspective, Eq. (2)](#private-perspective)
4. [Ratepayer perspective, Eq. (3)](#ratepayer-perspective)
5. [Social perspective, Eqs. (4)–(5)](#social-perspective)
6. [Metrics and the net-benefit test, Eqs. (6)–(8)](#metrics-and-the-net-benefit-test)
7. [Staged service, Eq. (9)](#staged-service)
8. [Realization decomposition, Eq. (10)](#realization-decomposition)
9. [Relations stated in the text](#relations-stated-in-the-text)
10. [Conventions of this implementation](#conventions-of-this-implementation)
11. [Scope](#scope)

## Symbols

| Symbol | Meaning | Unit | Code |
|---|---|---|---|
| $`P_I`$ | delayed IT capacity (server and networking load) | MW-IT | `Project.it_capacity_mw` |
| $`\mathrm{PUE}`$ | power usage effectiveness | – | `Project.pue` |
| $`\mathrm{pf}`$ | power factor | – | `Project.power_factor` |
| $`P_G`$ | facility-level grid demand, $`\mathrm{PUE}\,P_I`$ | MW | `Project.grid_mw` |
| $`S`$ | interconnection apparent power, $`P_G/\mathrm{pf}`$ | MVA | `Project.interconnection_mva` |
| $`\tau`$ | delay: months between the planned service date and first usable grid service | month | `Scenario.delay_months` |
| $`t`$ | month of the delay, $`t = 1,\dots,\tau`$ | – | |
| $`r`$ | annual discount rate | – | `Scenario.discount_rate_annual` |
| $`d_t`$ | monthly discount factor, $`(1+r)^{-t/12}`$ | – | `discount_factor` |
| $`q`$ | probability that the project is realized | – | `PrivateInputs.realization_probability` |
| $`s`$ | fraction of gross margin recovered through the developer's own arrangements during the delay | – | `PrivateInputs.substitution_fraction` |
| $`V`$ | gross value | USD per MW-IT-month | `PrivateInputs.gross_value_usd_per_mw_it_month` |
| $`\mu`$ | operating margin | – | `PrivateInputs.operating_margin` |
| $`K`$ | committed capital cost | USD per MW-IT | `PrivateInputs.committed_capital_usd_per_mw_it` |
| $`c`$ | committed capital fraction | – | `PrivateInputs.committed_capital_fraction` |
| $`\alpha_t`$ | capital deployment profile, with peak level $`a`$ | – | `deployment_fraction`; `PrivateInputs.deployment_profile`, `.deployment_peak` |
| $`i`$ | annual carrying rate on committed capital | – | `PrivateInputs.carrying_rate_annual` |
| $`\pi^{\mathrm{contract}}`$ | contract penalties | USD per MW-IT-month | `PrivateInputs.contract_penalty_usd_per_mw_it_month` |
| $`\pi^{\mathrm{mit}}`$ | mitigation premiums | USD per MW-IT-month | `PrivateInputs.mitigation_premium_usd_per_mw_it_month` |
| $`U`$ | utility upgrade cost | USD per grid MW | `RatepayerInputs.upgrade_cost_usd_per_grid_mw` |
| $`i_u`$ | annual utility carrying rate | – | `RatepayerInputs.utility_carrying_rate_annual` |
| $`\rho`$ | residual ratepayer share after tariff protections | – | `RatepayerInputs.residual_share` |
| $`\phi_u`$ | probability that the upgrade is financed during the delay | – | `RatepayerInputs.financing_probability` or the financing rule |
| $`\phi_s`$ | stranding probability conditional on financing | – | the financing rule (see the text relations) |
| $`p_a`$ | probability that a realized project's upgrade is stranded anyway | – | `RatepayerInputs.abandonment_probability` |
| $`h`$, $`p_h`$ | substitute pathway that fills the delay, and its probability | – | `BridgeInputs.pathway_probability` |
| $`C^{\mathrm{em}}_t`$, $`C^{\mathrm{rel}}_t`$, $`C^{\mathrm{loc}}_t`$ | monetized emissions, reliability and local impacts in month $`t`$ | USD | `social_cost` |
| $`E_t`$ | electricity served by the pathway in month $`t`$ | MWh | `bridge_pathway` |
| $`\epsilon_h`$, $`\epsilon_0`$ | direct emission factor of the pathway and of the on-time counterfactual | t CO₂/MWh | `BridgeInputs` |
| $`v_t`$ | social cost of CO₂ | USD/t CO₂ | `bridge_pathway` argument |
| $`m`$, $`\tau_1(m)`$ | acceleration option and the delay it achieves ($`\tau_0`$: the delay without it) | –, month | `avoided_cost` |
| $`C^{\mathrm{add}}_m`$ | implementation cost of option $`m`$ borne by others | USD | `net_benefit` |
| $`f`$, $`\tau_e`$, $`g(f)`$ | staged service: fraction served early, month of first service, revenue-equivalent service fraction | –, month, – | `staged_private_cost` |
| $`A_\tau`$, $`B_\tau`$ | private terms weighted by $`q`$, and the carrying cost | USD | `realization_decomposition` |
| $`\eta_{C,q}`$ | elasticity of private CoDE with respect to $`q`$ | – | `realization_decomposition` |

All CoDE quantities are present values in USD.

## The CoDE vector

CoDE is a vector of present-value quantities by perspective:

```math
\mathbf{C}^{\mathrm{CoDE}} = \left(C^{\mathrm{priv}},\ C^{\mathrm{rate}},\ C^{\mathrm{soc}}\right) \qquad (1)
```

- $`C^{\mathrm{priv}}`$ is borne by the developer or customer, $`C^{\mathrm{rate}}`$ by the utility and its ratepayers, and $`C^{\mathrm{soc}}`$ is any external cost not internalized by the other two.
- The three are not added: $`C^{\mathrm{priv}}`$ contains transfers to counterparties outside the model, the split between $`C^{\mathrm{priv}}`$ and $`C^{\mathrm{rate}}`$ is itself a tariff choice, and $`C^{\mathrm{soc}}`$ is incomplete. Eq. (8) states the test under which they may be combined.
- Code: `code_vector` returns a `CodeVector` with the three components and no total.

## Private perspective

Lost operating margin, carrying cost on committed capital, contract penalties and mitigation premiums:

```math
C^{\mathrm{priv}}(P_I,\tau) = \sum_{t=1}^{\tau} d_t\,P_I \Big[ q(1-s)V\mu + \pi^{\mathrm{contract}} + \pi^{\mathrm{mit}} + K\,c\,\alpha_t\,i/12 \Big] \qquad (2)
```

- Margin is weighted by $`q`$ because it accrues only if the project proceeds.
- The carrying term has no $`q`$ weight: committed capital is financed either way, and abandonment, if it occurs, is assumed to resolve after the delay window, so carrying cost accrues over the full $`\tau`$ with profile $`c\,\alpha_t`$.
- The contract and mitigation terms are unweighted: penalties are triggered by the delay itself and mitigation premiums are paid while it lasts.
- Code: `private_cost` (present values of the four terms and their total); `private_monthly` (the same month by month, undiscounted and discounted).

## Ratepayer perspective

Expected utility carrying cost for network upgrades, and exposure to stranded assets:

```math
C^{\mathrm{rate}}(\tau) = \sum_{t=1}^{\tau} d_t\,P_G\,U\,i_u\,\rho\,\phi_u/12 \;+\; d_{\tau}\,P_G\,U\,\rho\,\phi_u\,\phi_s \qquad (3)
```

- A single $`\rho`$ covers both terms.
- At $`\tau = 0`$ the carrying sum is empty but the stranding term is not: part of the level is exposure that a financed request carries whatever its timing. The delay-attributable cost is the differential $`\Delta C^{\mathrm{rate}}(\tau) = C^{\mathrm{rate}}(\tau) - C^{\mathrm{rate}}(0)`$, and this differential, not the level, is comparable with $`C^{\mathrm{priv}}`$.
- Code: `ratepayer_cost` (carrying, stranding, total, and the $`\phi_u`$, $`\phi_s`$ used); `ratepayer_delay_cost` ($`\Delta C^{\mathrm{rate}}`$).

## Social perspective

The social perspective is pathway-specific: it prices the external effects of whatever substitute fills the delay (bridge power, relocation, curtailment, staged service). For a pathway $`h`$ used with probability $`p_h`$:

```math
C^{\mathrm{soc}}(h) = p_h \sum_{t=1}^{\tau} d_t \left( C^{\mathrm{em}}_t(h) + C^{\mathrm{rel}}_t(h) + C^{\mathrm{loc}}_t(h) \right) \qquad (4)
```

For an emissions-only pathway the first term becomes

```math
C^{\mathrm{soc,em}}(h) = p_h \sum_{t=1}^{\tau} d_t\,E_t(h) \left[ \epsilon_h(t) - \epsilon_0(t) \right] v_t \qquad (5)
```

- $`\epsilon_h - \epsilon_0`$ is the pathway's incremental direct emission factor relative to the on-time counterfactual.
- The counterfactual $`\epsilon_0`$ should be the marginal grid intensity; average factors from public data are a proxy for it.
- $`p_h = q`$ holds only when every realized project uses pathway $`h`$.
- Code: `social_cost` (Eq. 4, monthly terms as scalars or arrays); `emissions_social_cost` (Eq. 5); `bridge_pathway` (Eq. 5 for a temporary-supply pathway, see the conventions).

## Metrics and the net-benefit test

**Delay cost intensity** (DCI) expresses CoDE per unit of delayed capacity per month, in USD per MW-IT-month for the private perspective and USD per grid-MW-month for the ratepayer perspective:

```math
\mathrm{DCI}^{\mathrm{priv}} = \frac{C^{\mathrm{priv}}}{P_I\,\tau}, \qquad \mathrm{DCI}^{\mathrm{rate}} = \frac{\Delta C^{\mathrm{rate}}}{P_G\,\tau} \qquad (6)
```

**Avoided cost.** If an option $`m`$ (a utility upgrade, a staged energization agreement, flexible interconnection, relocation or a temporary supply arrangement) shortens the delay from $`\tau_0`$ to $`\tau_1(m)`$:

```math
\Delta C^{\mathrm{priv}}_m = C^{\mathrm{priv}}(P_I,\tau_0) - C^{\mathrm{priv}}(P_I,\tau_1(m)) \qquad (7)
```

- $`\Delta C^{\mathrm{rate}}_m`$ is defined the same way from $`C^{\mathrm{rate}}`$; the $`\tau = 0`$ stock is common to both of its terms and cancels.
- The added pathway externality is $`\Delta C^{\mathrm{soc}}_m = C^{\mathrm{soc}}(m) - C^{\mathrm{soc}}(\text{on time})`$, normally positive.
- The **break-even acceleration payment** (BEAP) is the scalar $`\Delta C^{\mathrm{priv}}_m`$: the most a developer can justify from avoided delay cost alone. $`[\,C^{\mathrm{add}}_m,\ \mathrm{BEAP}\,]`$ is the bargaining range against the implementation cost $`C^{\mathrm{add}}_m`$ borne by others. The option is privately worth doing when $`\mathrm{BEAP} \ge C^{\mathrm{add}}_m`$, under risk neutrality and ignoring the option value of waiting.

**Net-benefit test.** Option $`m`$ is potentially welfare-improving when

```math
\Delta C^{\mathrm{priv}}_m + \Delta C^{\mathrm{rate}}_m - C^{\mathrm{add}}_m - \Delta C^{\mathrm{soc}}_m > 0 \qquad (8)
```

and distributionally acceptable when the developer's payment covers $`C^{\mathrm{add}}_m`$ plus compensation for $`\Delta C^{\mathrm{soc}}_m`$. Part of $`\Delta C^{\mathrm{priv}}_m`$ may be scarcity rent reallocated rather than created, so reporting it gross makes the left side of Eq. (8) an upper bound on the welfare gain. BEAP alone answers neither question; it is one input to both.

Code: `delay_cost_intensity` (Eq. 6); `avoided_cost` returns `AvoidedCost(private, ratepayer)` with `.beap` (Eq. 7); `net_benefit` (Eq. 8, with `privately_worthwhile` and `implementation_cost_bound`); `distributionally_acceptable`.

## Staged service

A fraction $`f`$ of IT capacity receives service after $`\tau_e < \tau_0`$ months while the rest waits until $`\tau_0`$. The revenue-equivalent service fraction $`g(f)`$ scales both the margin and the carrying term, with $`g(f) = f`$ in the benchmark:

```math
C^{\mathrm{priv}}_{\mathrm{stage}} = C^{\mathrm{priv}}\big(g(f)P_I,\tau_e\big) + C^{\mathrm{priv}}\big((1-g(f))P_I,\tau_0\big) \qquad (9)
```

$`C^{\mathrm{priv}}(P_I,\tau_0) - C^{\mathrm{priv}}_{\mathrm{stage}}`$ is the private value of partial service.

Code: `staged_private_cost(scenario, tau_e, f, revenue_equivalent=g)`; `acceleration_options` tabulates staged and full-service options.

## Realization decomposition

Under the delay–realization dependence stress (see the text relations), private CoDE decomposes as

```math
C^{\mathrm{priv}}(\tau,\beta) = q_\beta(\tau)\,A_\tau + B_\tau, \qquad \eta_{C,q} = \frac{\partial \ln C^{\mathrm{priv}}}{\partial \ln q} = \frac{q_\beta A_\tau}{q_\beta A_\tau + B_\tau} \qquad (10)
```

where $`A_\tau = \sum_t d_t P_I (1-s) V \mu`$ collects the terms weighted by realization probability and $`B_\tau = \sum_t d_t P_I K c \alpha_t i/12`$ is the carrying cost. The elasticity shows how far realization risk can move private CoDE when the carrying cost does not depend on $`q`$.

Code: `realization_decomposition` (A, B, elasticity); `dependence_stress` (Eq. 10 along a $`q_\beta`$ curve).

## Relations stated in the text

| Relation | Content | Code |
|---|---|---|
| $`P_G = \mathrm{PUE}\,P_I`$, $`S = P_G/\mathrm{pf}`$ | delayed IT capacity to facility grid MW and interconnection MVA | `Project.grid_mw`, `Project.interconnection_mva` |
| $`d_t = (1+r)^{-t/12}`$ | monthly discount factor at annual rate $`r`$ | `discount_factor` |
| $`x_t = \min\{t/\tau, 1\}`$; $`\alpha_t = a`$, $`a x_t`$, $`a\min\{1, 2x_t\}`$, $`a x_t^2`$ | static, linear, front-loaded and back-loaded capital deployment, with build progress advancing over the delay window | `deployment_fraction` |
| $`\phi_s = (1-q) + q\,p_a`$, $`\phi_u`$ set independently of $`q`$ | milestone-based financing: non-realization enters through the stranding probability | `RatepayerInputs(financing_rule="milestone")` |
| $`\phi_u = q`$, $`\phi_s = p_a`$ | realization-linked financing: the utility commits only once the project goes forward | `RatepayerInputs(financing_rule="realization_linked")` |
| $`\Delta C^{\mathrm{rate}}(\tau) = C^{\mathrm{rate}}(\tau) - C^{\mathrm{rate}}(0)`$ | delay-attributable ratepayer cost | `ratepayer_delay_cost` |
| $`q_\beta(\tau) = \min\{1,\ q^{*}\exp[-\beta(\tau - \tau^{*})/12]\}`$ | delay–realization dependence: $`\beta`$ (per year) sets how fast realization probability declines per additional year of delay; every curve passes through $`q^{*}`$ at the anchor delay $`\tau^{*}`$ | `realization_curve` |

## Conventions of this implementation

- **Time and units:**
  - Present values are at the planned service date (month 0); the months of the delay are $`t = 1,\dots,\tau`$, and $`d_0 = 1`$.
  - Money in USD; capacity in MW-IT ($`P_I`$) or grid MW ($`P_G`$); apparent power in MVA; time in months. Rates and probabilities are fractions (0.08, not 8).
  - Market rates quoted in USD/kW-month convert with `usd_per_kw_month_to_usd_per_mw_month` (× 1,000).
  - Emission factors in lb CO₂/kWh convert with `lb_per_kwh_to_t_per_mwh`.
- **Deployment profile inside a cost:** $`\alpha_t`$ is evaluated in the window of the cost being computed. In Eq. (9), $`C^{\mathrm{priv}}(\cdot,\tau_e)`$ uses $`x_t = t/\tau_e`$.
- **Stranding:** the expected write-off of Eq. (3) is booked once, at $`\tau`$, with the discount factor $`d_\tau`$.
- **Financing rules:** `RatepayerInputs.financing_rule` is `"milestone"` (give $`\phi_u`$ and $`p_a`$), `"realization_linked"` (give $`p_a`$) or `"explicit"` (give $`\phi_u`$ and $`\phi_s`$). Fields that the chosen rule does not use must be left unset.
- **DCI (Eq. 6):** undefined when $`\tau = 0`$ or the capacity is zero: NaN in Python, `null` in the JSON written by the command line.
- **Options (Eq. 7):** `avoided_cost(scenario, tau_1)` takes $`\tau_0`$ from the scenario. For a staged option, `acceleration_options` reports the private value of partial service (Eq. 9) as its BEAP, and evaluates the ratepayer account with the same split of the request: $`g\,C^{\mathrm{rate}}(\tau_e) + (1-g)\,C^{\mathrm{rate}}(\tau_0)`$.
- **Bridge pathway** (`bridge_pathway`):
  - temporary supply serves the load in months $`1,\dots,b`$ of the delay, with $`E_t = P_G \times \text{utilization} \times 730`$ h;
  - the avoided private cost is the discounted sum of the private terms of Eq. (2) in those months, evaluated in the $`\tau_0`$ window (the carrying saving included);
  - the upgrade schedule does not change, so the ratepayer account does not change;
  - $`\Delta C^{\mathrm{soc}}_m`$ is Eq. (5) over the $`b`$ bridged months; `discount_damages=False` sets $`d_t = 1`$, and `dollar_factor` converts the dollar year of $`v_t`$;
  - `implementation_cost_bound_usd` is the strict upper bound on $`C^{\mathrm{add}}_m`$ for Eq. (8) to hold, in total and per MWh bridged;
  - the wrapper applies when every realized project uses the bridge ($`p_h = q`$, taken from the scenario) and the bridge serves the facility's load (utilization above zero); for another pathway probability, price the emissions with `emissions_social_cost` and the private side separately.
- **Eq. (8):** `net_benefit` uses the strict inequality; `implementation_cost_bound` $`= \Delta C^{\mathrm{priv}}_m + \Delta C^{\mathrm{rate}}_m - \Delta C^{\mathrm{soc}}_m`$ is a strict upper bound: Eq. (8) holds when $`C^{\mathrm{add}}_m`$ is below it, and the net benefit is zero at the bound.
- **Eq. (10) with non-zero $`\pi`$ terms:** the present value $`\Pi_\tau`$ of the unweighted contract and mitigation terms joins the denominator, $`\eta_{C,q} = q A_\tau/(q A_\tau + B_\tau + \Pi_\tau)`$. With $`\pi^{\mathrm{contract}} = \pi^{\mathrm{mit}} = 0`$ this is Eq. (10).
- **Dependence stress** (`dependence_stress`): two ratepayer differentials are reported. `ratepayer_delay_usd` nets the level at $`\tau`$ against an on-time path evaluated at $`q_\beta(0)`$, so on-time service is also credited with preventing delay-induced attrition; `ratepayer_delay_fixed_q_usd` evaluates the on-time path at $`q^{*}`$ instead, which isolates the timing effect.

## Scope

As stated in the article:

- CoDE takes the timing and quantity of usable service as given and prices the consequences; it does not model why service is late.
- The MW/MVA conversion gives request scale only. Bus-level feasibility, thermal and voltage limits, contingencies and lead times require a network study whose results become CoDE inputs.
- The upgrade is charged at full cost from month one, while developer capital follows a deployment profile.
- $`C^{\mathrm{priv}}`$ counts within-window costs only.
- An emissions-only bridge pathway monetizes direct CO₂ differences; upstream methane, local pollution, water and reliability effects belong to the other terms of Eq. (4).
- Applications should replace assumed ranges with service-request, project, tariff and pathway data.
