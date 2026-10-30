"""Scenario sets: full-factorial lattices, Latin hypercube screening and rank correlations.

Parameters are addressed by path, e.g. ``"delay_months"``, ``"project.it_capacity_mw"``,
``"private.operating_margin"``, ``"ratepayer.residual_share"`` (see
:func:`code_delay.parameters.set_parameter`). Cases are unweighted: percentiles of a
lattice summarize the lattice, not a distribution over projects.
"""

from __future__ import annotations

import itertools
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .accounting import delay_cost_intensity, private_cost, ratepayer_cost, ratepayer_delay_cost
from .parameters import Scenario, get_parameter, set_parameters


def evaluate(scenarios: Iterable[Scenario], parameters: list[str] | None = None) -> pd.DataFrame:
    """One row per scenario: chosen inputs, private and ratepayer components, DCI (USD)."""
    rows = []
    for s in scenarios:
        priv = private_cost(s)
        rate = ratepayer_cost(s)
        dci = delay_cost_intensity(s)
        row: dict[str, Any] = {"name": s.name}
        for p in parameters or []:
            row[p] = get_parameter(s, p)
        row.update({"private_usd": priv["total"], "lost_margin_usd": priv["lost_margin"],
                    "carrying_usd": priv["carrying"], "contract_penalty_usd": priv["contract_penalty"],
                    "mitigation_premium_usd": priv["mitigation_premium"],
                    "ratepayer_level_usd": rate["total"], "ratepayer_delay_usd": ratepayer_delay_cost(s),
                    "ratepayer_stranding_usd": rate["stranding"],
                    "private_dci_usd_per_mw_it_month": dci["private_usd_per_mw_it_month"],
                    "ratepayer_dci_usd_per_grid_mw_month": dci["ratepayer_usd_per_grid_mw_month"]})
        rows.append(row)
    return pd.DataFrame(rows)


def full_factorial(base: Scenario, grid: dict[str, list[Any]]) -> list[Scenario]:
    """Every combination of the listed values; other parameters stay at ``base``."""
    if not grid:
        return [base]
    keys = list(grid)
    for k in keys:
        get_parameter(base, k)
        if not isinstance(grid[k], (list, tuple)) or not grid[k]:
            raise ValueError(f"grid[{k!r}] must be a non-empty list")
    return [set_parameters(base, {**dict(zip(keys, combo)), "name": f"case_{i:06d}"})
            for i, combo in enumerate(itertools.product(*(grid[k] for k in keys)))]


def latin_hypercube(n_samples: int, n_dims: int, seed: int) -> np.ndarray:
    """n-by-d Latin hypercube on [0, 1): one draw per stratum in every column."""
    if n_samples < 1 or n_dims < 1:
        raise ValueError("n_samples and n_dims must be at least 1")
    rng = np.random.default_rng(seed)
    out = np.empty((n_samples, n_dims))
    for j in range(n_dims):
        out[:, j] = rng.permutation((np.arange(n_samples) + rng.random(n_samples)) / n_samples)
    return out


def sample_scenarios(base: Scenario, ranges: dict[str, tuple[float, float]], n_samples: int, seed: int,
                     categorical: dict[str, list[Any]] | None = None) -> list[Scenario]:
    """Latin hypercube over continuous ``ranges`` (uniform) and ``categorical`` choices (equal shares)."""
    categorical = categorical or {}
    both = set(ranges) & set(categorical)
    if both:
        raise ValueError(f"parameters given as both continuous and categorical: {sorted(both)}")
    names = list(ranges) + list(categorical)
    for n in names:
        get_parameter(base, n)
    for n, (lo, hi) in ranges.items():
        if not (np.isfinite(lo) and np.isfinite(hi)) or hi < lo:
            raise ValueError(f"range for {n!r} must be finite with low <= high")
    for n, choices in categorical.items():
        if not isinstance(choices, (list, tuple)) or not choices:
            raise ValueError(f"categorical choices for {n!r} must be a non-empty list")
    unit = latin_hypercube(n_samples, len(names), seed)
    out = []
    for i in range(n_samples):
        values: dict[str, Any] = {}
        for j, n in enumerate(names):
            u = float(unit[i, j])
            if n in ranges:
                lo, hi = ranges[n]
                values[n] = lo + u * (hi - lo)
            else:
                choices = categorical[n]
                values[n] = choices[min(int(u * len(choices)), len(choices) - 1)]
        out.append(set_parameters(base, {**values, "name": f"lhs_{i:05d}"}))
    return out


def rank_correlations(table: pd.DataFrame, inputs: list[str], targets: list[str],
                      categorical: list[str] | None = None) -> pd.DataFrame:
    """Spearman rank correlations of inputs (categorical ones as 0/1 dummies) with targets.

    They scale with the ranges sampled, so they order sensitivity within those ranges only.
    """
    data = table.copy()
    columns = list(inputs)
    for c in categorical or []:
        dummies = pd.get_dummies(data[c], prefix=c).astype(float)
        data = pd.concat([data, dummies], axis=1)
        columns.extend(dummies.columns)
    rows = []
    for t in targets:
        tr = data[t].rank(method="average")
        constant_target = data[t].nunique() <= 1
        for c in columns:
            x = data[c].astype(float)
            # undefined (NaN) when either side does not vary
            rho = float("nan") if constant_target or x.nunique() <= 1 else float(x.rank(method="average").corr(tr))
            rows.append({"target": t, "input": c, "spearman": rho, "abs_spearman": abs(rho)})
    out = pd.DataFrame(rows)
    return out.sort_values(["target", "abs_spearman"], ascending=[True, False], ignore_index=True)


def percentiles_by(table: pd.DataFrame, by: str, target: str, quantiles=(0.05, 0.25, 0.5, 0.75, 0.95)) -> pd.DataFrame:
    """Unweighted percentiles of ``target`` within each value of ``by``."""
    q = table.groupby(by)[target].quantile(list(quantiles)).unstack()
    q.columns = [f"p{int(round(x * 100)):02d}" for x in q.columns]
    return q.reset_index()


def tariff_cases(base: Scenario, cases: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Ratepayer level and delay differential for named sets of tariff-related overrides.

    Each case's overrides are applied together (``set_parameters``), so a case may change
    the financing rule and unset the fields it no longer uses (value ``None``).
    """
    rows = []
    for name, overrides in cases.items():
        s = set_parameters(base, overrides)
        rate = ratepayer_cost(s)
        rows.append({"case": name, **overrides, "private_usd": private_cost(s)["total"],
                     "ratepayer_level_usd": rate["total"], "ratepayer_delay_usd": ratepayer_delay_cost(s),
                     "ratepayer_stranding_usd": rate["stranding"]})
    return pd.DataFrame(rows)
