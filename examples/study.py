"""The study tools on illustrative inputs: lattice, Latin hypercube screening, dependence stress, tariff stress.

Illustrative inputs and ranges (code_delay.illustrative): the numbers say nothing about any real project.
Run: python examples/study.py [--out-dir outputs/study]
"""

import argparse
from pathlib import Path

from code_delay import (dependence_stress, evaluate, full_factorial, illustrative_scenario, percentiles_by,
                        rank_correlations, sample_scenarios, tariff_cases, write_table)
from code_delay.illustrative import (ILLUSTRATIVE_CATEGORICAL, ILLUSTRATIVE_GRID, ILLUSTRATIVE_RANGES,
                                     ILLUSTRATIVE_TARIFF_CASES)

parser = argparse.ArgumentParser()
parser.add_argument("--out-dir", default=None)
args = parser.parse_args()
M = 1e6
s = illustrative_scenario()

lattice = evaluate(full_factorial(s, ILLUSTRATIVE_GRID), parameters=list(ILLUSTRATIVE_GRID))
print(f"Lattice: {len(lattice)} unweighted cases")
pct = percentiles_by(lattice, "delay_months", "private_usd")
print((pct.set_index("delay_months") / M).round(1).to_string())

samples = evaluate(sample_scenarios(s, ILLUSTRATIVE_RANGES, n_samples=500, seed=7, categorical=ILLUSTRATIVE_CATEGORICAL),
                   parameters=list(ILLUSTRATIVE_RANGES) + list(ILLUSTRATIVE_CATEGORICAL))
corr = rank_correlations(samples, list(ILLUSTRATIVE_RANGES), ["private_usd", "ratepayer_level_usd"],
                         categorical=list(ILLUSTRATIVE_CATEGORICAL))
print("\nLargest rank correlations (within the illustrative ranges only):")
print(corr.groupby("target").head(4)[["target", "input", "spearman"]].round(3).to_string(index=False))

dep = dependence_stress(s, betas_per_year=[0.0, 0.08, 0.15], delays_months=[9, 30, 48])
print("\nDelay-realization dependence (MUSD):")
cols = ["private_usd", "ratepayer_level_usd", "ratepayer_delay_usd", "ratepayer_delay_fixed_q_usd"]
view = dep.assign(**{c: dep[c] / M for c in cols})[["beta_per_year", "delay_months", "realization_probability",
                                                      "elasticity_q"] + cols]
print(view.round(3).to_string(index=False))

tar = tariff_cases(s, ILLUSTRATIVE_TARIFF_CASES)
print("\nTariff stress (MUSD):")
cols = ["private_usd", "ratepayer_level_usd", "ratepayer_delay_usd"]
print(tar.assign(**{c: tar[c] / M for c in cols})[["case"] + cols].round(1).to_string(index=False))

if args.out_dir:
    out = Path(args.out_dir)
    for name, table in {"lattice": lattice, "lhs_samples": samples, "rank_correlations": corr,
                        "dependence": dep, "tariff": tar}.items():
        write_table(table, out / f"{name}.csv")
    print(f"\nwrote tables to {out}")
