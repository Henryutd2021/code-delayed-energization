# CoDE framework: the Cost of Delayed Energization for AI data centers

A documented, runnable implementation of the framework in:

> Honglin Li and Buxin She. **Quantifying the Cost of Delayed Energization (CoDE) for AI Data Centers.** *2026 North American Power Symposium (NAPS)*, accepted.

Grid interconnection has become a binding constraint on large data-center projects. CoDE prices the interval that a planned large load spends waiting for its first usable grid service. It maps the delayed IT capacity to grid MW and interconnection MVA, and it keeps the delay cost in three separate accounts: the developer (private), the utility and its ratepayers, and society. Two metrics make the results comparable across project sizes, delays and mitigation options: the delay cost intensity (DCI) and the break-even acceleration payment (BEAP). A net-benefit test states when the accounts may be combined.

## Research question

How large is the cost of delayed grid energization for a data center, who bears it (the developer, ratepayers, or society), and how should acceleration options such as staged service or bridge power be valued against their implementation cost and externalities?

## Framework at a glance

| Element | Content | Article |
|---|---|---|
| Request scale | $`P_G = \mathrm{PUE}\,P_I`$ grid MW, $`S = P_G/\mathrm{pf}`$ MVA | Section II |
| CoDE vector | $`(C^{\mathrm{priv}}, C^{\mathrm{rate}}, C^{\mathrm{soc}})`$, present values, not added | Eq. (1) |
| Private | lost margin weighted by realization probability, carrying cost on committed capital with a deployment profile, contract penalties, mitigation premiums | Eq. (2) |
| Ratepayer | expected utility carrying cost plus expected stranding; delay-attributable part $`C^{\mathrm{rate}}(\tau) - C^{\mathrm{rate}}(0)`$ | Eq. (3) |
| Social | pathway-specific external costs; emissions-only form with a social cost of CO₂ | Eqs. (4)–(5) |
| Metrics | DCI per MW-month; avoided cost and BEAP of an acceleration option; net-benefit test | Eqs. (6)–(8) |
| Staged service | part of the capacity served early with a revenue-equivalent fraction $`g(f)`$ | Eq. (9) |
| Realization risk | decomposition of private CoDE and its elasticity with respect to realization probability | Eq. (10) |
| Study tools | full-factorial lattice, Latin hypercube screening with rank correlations, delay–realization dependence, tariff stress, bridge-power pathway | Section III |

The complete mathematics, with the article's equation numbers, is in [docs/formulation.md](docs/formulation.md).

## What is in this repository

| Path | Content |
|---|---|
| [`docs/formulation.md`](docs/formulation.md) | symbols, Eqs. (1)–(10), the relations the article states in the text, implementation conventions, scope |
| [`docs/data_pipeline.md`](docs/data_pipeline.md) | the kind of public source behind each parameter, the provenance rule, preparation steps, the scenario file schema and the output tables |
| [`docs/scenarios.md`](docs/scenarios.md) | the article's study design (base case, lattice, screening, dependence stress, staged service, tariff stress, bridge pathway) and how to set up each part |
| [`docs/architecture.md`](docs/architecture.md) | modules, data flow, computation, tests |
| [`src/code_delay/`](src/code_delay/) | the implementation (NumPy and pandas only), scenario files, scenario sets, command line |
| [`examples/`](examples/) | `minimal.py` (one scenario), `study.py` (lattice, screening, dependence and tariff stress), `options.py` (staged service, bridge pathway, net-benefit test); all on illustrative inputs |
| [`tests/`](tests/) | pytest suite (see docs/architecture.md) |

## Quick start

```bash
git clone https://github.com/Henryutd2021/code-delayed-energization.git
cd code-delayed-energization
python -m venv .venv && source .venv/bin/activate      # Python 3.10 or newer (tested with 3.12)
pip install -e ".[test]"
python examples/minimal.py
pytest
```

With conda instead: `conda env create -f environment.yml && conda activate code-delay && pip install -e .`

The command line works on scenario files:

```bash
code-delay example my_scenario.json --grid grid.json --ranges ranges.json   # illustrative scenario, grid and ranges
code-delay run my_scenario.json --out-dir outputs/run                 # CoDE vector, components, DCI, monthly table
code-delay staged my_scenario.json --first-service 9 18 --fractions 0.3 0.6 1 --out outputs/staged.csv
code-delay sweep my_scenario.json grid.json --out outputs/lattice.csv
code-delay lhs my_scenario.json ranges.json --samples 500 --seed 1 --out-dir outputs/lhs
```

In Python:

```python
from code_delay import (read_scenario, code_vector, ratepayer_delay_cost, delay_cost_intensity,
                        avoided_cost, net_benefit)

s = read_scenario("my_scenario.json")                    # your own inputs, see docs/data_pipeline.md
print(code_vector(s))                                    # (private, ratepayer, social); never added
print(ratepayer_delay_cost(s), delay_cost_intensity(s))
option = avoided_cost(s, shortened_delay_months=18)      # Eq. (7): BEAP and avoided ratepayer cost
print(net_benefit(option.private, option.ratepayer, implementation_cost=50e6, added_social=0.0))
```

**About the example inputs:** `code_delay.illustrative` holds invented round values. They show how the framework behaves and how to read its output. Their results say nothing about any real market, utility or project.

## Using your own data

1. Collect the parameters with their provenance ([docs/data_pipeline.md](docs/data_pipeline.md)). Label values without a public anchor as assumptions or sensitivities.
2. Write a scenario file; it is validated when read (units are part of the field names, every value must be finite and in range).
3. Run the base case and the study parts you need ([docs/scenarios.md](docs/scenarios.md)), and report the three accounts separately.

## What this repository does not contain

This repository presents the modelling framework. It does not contain the code, the parameter files or the results used for the accepted article. For the article's results, see the article.

## Citation

If you use this framework, please cite the article above. Citation metadata for both the article and this software are in [`CITATION.cff`](CITATION.cff).

## Licence

- Code: [MIT](LICENSE).
- Documentation (`README.md`, `docs/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
