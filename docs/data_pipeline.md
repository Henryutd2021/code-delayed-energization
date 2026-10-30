# Data pipeline

CoDE is an accounting framework: its inputs are parameters, not time series. This document describes where each parameter can come from, how to record its provenance, and the file formats the package reads and writes. No data are shipped; `code_delay.illustrative` holds invented round values for the examples.

## Contents

1. [Parameter sources](#parameter-sources)
2. [Provenance rule](#provenance-rule)
3. [Preparation steps](#preparation-steps)
4. [Scenario file](#scenario-file)
5. [Grid, ranges and case files](#grid-ranges-and-case-files)
6. [Output tables](#output-tables)

## Parameter sources

The article builds its benchmark from public reports, filings and agency publications, and labels every value that has no public anchor as an assumption or a sensitivity. The table lists the kind of source for each parameter. The article's benchmark values are in its Table II.

| Parameter | Kind of public source | How it becomes an input |
|---|---|---|
| $`P_I`$, $`\tau`$ | data-center capacity outlooks, reliability assessments, market reports on grid-connection waits, interconnection-queue studies | case sizes and delay bins spanning short to severe delays (scenario values, not observations) |
| $`V`$ | market reports on wholesale colocation asking rates | quoted in USD/kW-month; convert to USD per MW-IT-month (× 1,000) |
| $`\mu`$ | operator financial results (revenue and adjusted EBITDA) | a corporate margin is a proxy, not a project margin; use it as one end of a range |
| $`K`$ | construction-cost outlooks (shell and core; AI fit-out) | USD per MW-IT; state whether IT equipment is included |
| $`r`$, $`i`$, $`i_u`$ | none universal | WACC-style sensitivity values |
| $`q`$, $`s`$, $`c`$, $`a`$, profile | none observable for a project | assumptions or sensitivities; $`q`$ reflects the gap between announced and realized capacity |
| $`\mathrm{PUE}`$, $`\mathrm{pf}`$ | benchmark engineering values | map MW-IT to grid MW and MVA for request scale |
| $`U`$, $`\rho`$, $`p_a`$, $`\phi_u`$ | large-load tariff briefs, tariff dashboards, utility tariff pages, regulatory fact sheets | protections (collateral, minimum bills, exit fees, contributions in aid of construction) lower $`\rho`$; replace placeholders with case data |
| $`\pi^{\mathrm{contract}}`$, $`\pi^{\mathrm{mit}}`$ | not public for most projects | zero unless project data exist |
| $`\epsilon_h`$, $`\epsilon_0`$ | agency emission factors by fuel and for all generation | lb CO₂/kWh to t CO₂/MWh (`lb_per_kwh_to_t_per_mwh`); $`\epsilon_0`$ should be a marginal factor, an average is a proxy |
| $`v_t`$ | agency social-cost-of-greenhouse-gas estimates | state the dollar year, emission year and discount basis; convert dollar years with `dollar_factor` |

## Provenance rule

Record every value in a provenance table before it enters a scenario:

| Column | Content |
|---|---|
| `parameter` | parameter path, e.g. `private.gross_value_usd_per_mw_it_month` |
| `values` | the value or values used |
| `status` | `public_reported`, `public_derived`, `assumption` or `sensitivity` |
| `source` | citation or URL with access date; `none` for assumptions |
| `rationale` | why this value or range |
| `model_use` | which perspective or scenario family it feeds |

Values without a public anchor are labelled `assumption` (a single benchmark value) or `sensitivity` (a range or set of bins), and results that depend on them are reported as sensitivity ranges, not forecasts.

## Preparation steps

1. **Define the request:** IT capacity, PUE and power factor; the planned service date and the delay or delay bins.
2. **Private inputs:** convert market rates to USD per MW-IT-month; choose $`\mu`$, $`s`$, $`q`$; set $`K`$, $`c`$, $`a`$ and the deployment profile for the capital already committed; choose $`r`$ and $`i`$.
3. **Ratepayer inputs:** upgrade cost per grid MW from the service study or a placeholder; the residual share after the applicable tariff protections; the financing rule (milestone-based or realization-linked) with $`\phi_u`$, $`p_a`$ (or $`\phi_s`$).
4. **Pathways:** for each substitute that fills the delay, its months, utilization, emission factors, pathway probability and the social cost of CO₂ with its dollar year.
5. **Checks** (made when a scenario is read): every value finite; fractions in $`[0, 1]`$; power factor in $`(0, 1]`$; PUE positive; months whole and non-negative; the financing rule's fields present and the others unset.

## Scenario file

JSON, read by `read_scenario` and written by `write_scenario`. Unknown or missing fields raise an error that names the file and the field.

```json
{
  "name": "my_project",
  "delay_months": 30,
  "discount_rate_annual": 0.07,
  "project": {"it_capacity_mw": 200.0, "pue": 1.3, "power_factor": 0.9},
  "private": {
    "gross_value_usd_per_mw_it_month": 180000.0,
    "operating_margin": 0.3,
    "realization_probability": 0.8,
    "substitution_fraction": 0.2,
    "committed_capital_usd_per_mw_it": 15000000.0,
    "committed_capital_fraction": 0.8,
    "deployment_peak": 0.6,
    "carrying_rate_annual": 0.07,
    "deployment_profile": "linear",
    "contract_penalty_usd_per_mw_it_month": 0.0,
    "mitigation_premium_usd_per_mw_it_month": 0.0
  },
  "ratepayer": {
    "upgrade_cost_usd_per_grid_mw": 1500000.0,
    "utility_carrying_rate_annual": 0.07,
    "residual_share": 0.4,
    "financing_rule": "milestone",
    "financing_probability": 0.85,
    "abandonment_probability": 0.15
  }
}
```

(The values are the illustrative ones of `code_delay.illustrative`, not a benchmark.)

| Field | Symbol | Unit | Range |
|---|---|---|---|
| `delay_months` | $`\tau`$ | month | whole, ≥ 0 |
| `discount_rate_annual` | $`r`$ | – | > −1 |
| `project.it_capacity_mw` | $`P_I`$ | MW-IT | ≥ 0 |
| `project.pue` | PUE | – | > 0 |
| `project.power_factor` | pf | – | (0, 1] |
| `private.gross_value_usd_per_mw_it_month` | $`V`$ | USD per MW-IT-month | ≥ 0 |
| `private.operating_margin` | $`\mu`$ | – | [0, 1] |
| `private.realization_probability` | $`q`$ | – | [0, 1] |
| `private.substitution_fraction` | $`s`$ | – | [0, 1] |
| `private.committed_capital_usd_per_mw_it` | $`K`$ | USD per MW-IT | ≥ 0 |
| `private.committed_capital_fraction` | $`c`$ | – | [0, 1] |
| `private.deployment_peak` | $`a`$ | – | [0, 1] |
| `private.carrying_rate_annual` | $`i`$ | – | ≥ 0 |
| `private.deployment_profile` | shape of $`\alpha_t`$ | – | `static`, `linear`, `front_loaded`, `back_loaded` |
| `private.contract_penalty_usd_per_mw_it_month` | $`\pi^{\mathrm{contract}}`$ | USD per MW-IT-month | ≥ 0, default 0 |
| `private.mitigation_premium_usd_per_mw_it_month` | $`\pi^{\mathrm{mit}}`$ | USD per MW-IT-month | ≥ 0, default 0 |
| `ratepayer.upgrade_cost_usd_per_grid_mw` | $`U`$ | USD per grid MW | ≥ 0 |
| `ratepayer.utility_carrying_rate_annual` | $`i_u`$ | – | ≥ 0 |
| `ratepayer.residual_share` | $`\rho`$ | – | [0, 1] |
| `ratepayer.financing_rule` | | – | `milestone`, `realization_linked`, `explicit` |
| `ratepayer.financing_probability` | $`\phi_u`$ | – | [0, 1]; `milestone`, `explicit` |
| `ratepayer.abandonment_probability` | $`p_a`$ | – | [0, 1]; `milestone`, `realization_linked` |
| `ratepayer.stranding_probability` | $`\phi_s`$ | – | [0, 1]; `explicit` |

## Grid, ranges and case files

Parameters are addressed by path: `delay_months`, `discount_rate_annual`, or `<group>.<field>` with group `project`, `private` or `ratepayer`.

`code-delay example scenario.json --grid grid.json --ranges ranges.json` writes complete illustrative files of each kind.

- **Grid** (`code-delay sweep`, `full_factorial`): `{"<path>": [value, ...], ...}`; every combination is evaluated.
- **Ranges** (`code-delay lhs`, `sample_scenarios`): `{"continuous": {"<path>": [low, high], ...}, "categorical": {"<path>": [choice, ...]}}`; continuous ranges are sampled uniformly, categories in equal shares.
- **Tariff cases** (`tariff_cases`, Python): `{"<case name>": {"<path>": value, ...}, ...}`. A case's overrides are applied together, so it may switch the financing rule and unset the fields that rule does not use (`null` in JSON, `None` in Python).
- A parameter may appear in `continuous` or in `categorical`, not in both. Whole-month fields (`delay_months`) belong in a grid, not in continuous ranges.

## Output tables

| Producer | Columns |
|---|---|
| `code-delay run` → `summary.json` | request scale (`grid_mw`, `interconnection_mva`); `private_usd`, `ratepayer_usd`, `social_usd` (Eq. 1); the private components; ratepayer carrying, stranding and delay differential; both DCIs (Eq. 6), written as `null` where undefined (zero delay or capacity) |
| `code-delay run` → `private_monthly.csv` | month, $`d_t`$, $`\alpha_t`$, the four private terms and their total, undiscounted and with a `pv_` prefix |
| `evaluate` (sweep, LHS samples) | chosen inputs; `private_usd` and its components; `ratepayer_level_usd`, `ratepayer_delay_usd`, `ratepayer_stranding_usd`; both DCIs |
| `rank_correlations` | target, input (categorical inputs as dummies), Spearman coefficient and its magnitude |
| `acceleration_options` / `code-delay staged` | option, month of first service, served fraction, `beap_usd`, `avoided_ratepayer_usd` |
| `bridge_pathway` | social cost of CO₂, bridge months, $`p_h`$, bridged energy, conditional and ex-ante incremental emissions, `added_social_usd`, avoided private and ratepayer cost, `implementation_cost_bound_usd` (strict upper bound on $`C^{\mathrm{add}}`$, total and per MWh) |
| `dependence_stress` | $`\beta`$, delay, $`q_\beta`$, private cost and components, $`\eta_{C,q}`$, ratepayer level and the two differentials |
| `tariff_cases` | case, overrides, private cost, ratepayer level, delay differential and stranding term |

All money columns are present values in USD at the planned service date.
