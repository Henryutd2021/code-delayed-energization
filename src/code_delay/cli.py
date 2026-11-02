"""Command line: ``code-delay {example,run,sweep,lhs,staged}``.

  code-delay example scenario.json [--grid g.json] [--ranges r.json]   illustrative scenario (and grid, ranges)
  code-delay run scenario.json --out-dir outputs/run     CoDE vector, components, DCI, monthly table
  code-delay sweep scenario.json grid.json --out f.csv   full-factorial lattice
  code-delay lhs scenario.json ranges.json --samples 500 --seed 1 --out-dir outputs/lhs
  code-delay staged scenario.json --first-service 9 18 --fractions 0.3 0.6 1 --out f.csv

grid.json:   {"<parameter path>": [values, ...], ...}
ranges.json: {"continuous": {"<path>": [low, high], ...}, "categorical": {"<path>": [choices]}}
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from .accounting import code_vector, delay_cost_intensity, private_cost, private_monthly, ratepayer_cost, \
    ratepayer_delay_cost
from .illustrative import ILLUSTRATIVE_CATEGORICAL, ILLUSTRATIVE_GRID, ILLUSTRATIVE_RANGES, illustrative_scenario
from .io import read_json, read_scenario, write_scenario, write_table
from .pathways import acceleration_options
from .sweeps import evaluate, full_factorial, rank_correlations, sample_scenarios

TARGETS = ["private_usd", "ratepayer_level_usd", "ratepayer_delay_usd"]


def _json(data) -> str:
    """Strict JSON: undefined values (NaN, e.g. DCI at a zero delay) are written as null."""
    clean = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in data.items()}
    return json.dumps(clean, indent=2, allow_nan=False)


def _write_json(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _run(args) -> None:
    s = read_scenario(args.scenario)
    vec = code_vector(s)
    priv = private_cost(s)
    rate = ratepayer_cost(s)
    summary = {"name": s.name, "it_capacity_mw": s.project.it_capacity_mw, "grid_mw": s.project.grid_mw,
               "interconnection_mva": s.project.interconnection_mva, "delay_months": s.delay_months,
               **vec.as_dict(), **{f"private_{k}_usd": v for k, v in priv.items() if k != "total"},
               "ratepayer_carrying_usd": rate["carrying"], "ratepayer_stranding_usd": rate["stranding"],
               "ratepayer_delay_usd": ratepayer_delay_cost(s), **delay_cost_intensity(s)}
    text = _json(summary)
    print(text)
    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_text(text + "\n", encoding="utf-8")
        write_table(private_monthly(s), out / "private_monthly.csv")
        print(f"wrote {out}/summary.json and {out}/private_monthly.csv")


def _sweep(args) -> None:
    s = read_scenario(args.scenario)
    grid = read_json(args.grid)
    if not isinstance(grid, dict):
        raise ValueError(f"{args.grid}: must be an object of parameter paths to value lists")
    table = evaluate(full_factorial(s, grid), parameters=list(grid))
    write_table(table, args.out)
    print(f"wrote {len(table)} cases to {args.out}")


def _lhs(args) -> None:
    s = read_scenario(args.scenario)
    spec = read_json(args.ranges)
    src = args.ranges
    if not isinstance(spec, dict) or "continuous" not in spec or set(spec) - {"continuous", "categorical"}:
        raise ValueError(f"{src}: expected an object with 'continuous' and optionally 'categorical'")
    continuous, categorical = spec["continuous"], spec.get("categorical", {})
    if not isinstance(continuous, dict) or not isinstance(categorical, dict):
        raise ValueError(f"{src}: 'continuous' and 'categorical' must be objects")
    ranges = {}
    for k, v in continuous.items():
        if not (isinstance(v, list) and len(v) == 2
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v)):
            raise ValueError(f"{src}: range for {k!r} must be [low, high] with finite numbers")
        ranges[k] = (float(v[0]), float(v[1]))
    for k, v in categorical.items():
        if not isinstance(v, list) or not v:
            raise ValueError(f"{src}: choices for {k!r} must be a non-empty list")
    table = evaluate(sample_scenarios(s, ranges, args.samples, args.seed, categorical),
                     parameters=list(ranges) + list(categorical))
    corr = rank_correlations(table, list(ranges), TARGETS, categorical=list(categorical))
    out = Path(args.out_dir)
    write_table(table, out / "samples.csv")
    write_table(corr, out / "rank_correlations.csv")
    print(f"wrote {len(table)} samples and {len(corr)} correlations to {out}")


def _staged(args) -> None:
    s = read_scenario(args.scenario)
    pairs = [(m, f) for m in args.first_service for f in args.fractions]
    table = acceleration_options(s, staged=pairs)
    write_table(table, args.out)
    print(f"wrote {len(table)} staged options to {args.out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code-delay", description="Cost of Delayed Grid Energization (CoDE) framework")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("example", help="write the illustrative scenario file (and optionally a grid and ranges)")
    p.add_argument("path")
    p.add_argument("--grid", help="also write the illustrative grid for `sweep`")
    p.add_argument("--ranges", help="also write the illustrative ranges for `lhs`")
    p = sub.add_parser("run", help="evaluate one scenario")
    p.add_argument("scenario")
    p.add_argument("--out-dir")
    p = sub.add_parser("sweep", help="full-factorial lattice")
    p.add_argument("scenario")
    p.add_argument("grid")
    p.add_argument("--out", required=True)
    p = sub.add_parser("lhs", help="Latin hypercube screening with rank correlations")
    p.add_argument("scenario")
    p.add_argument("ranges")
    p.add_argument("--samples", type=int, default=500)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out-dir", required=True)
    p = sub.add_parser("staged", help="staged-service options and their BEAP")
    p.add_argument("scenario")
    p.add_argument("--first-service", type=int, nargs="+", required=True)
    p.add_argument("--fractions", type=float, nargs="+", required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "example":
            write_scenario(illustrative_scenario(), args.path)
            if args.grid:
                _write_json(ILLUSTRATIVE_GRID, Path(args.grid))
            if args.ranges:
                _write_json({"continuous": {k: list(v) for k, v in ILLUSTRATIVE_RANGES.items()},
                             "categorical": ILLUSTRATIVE_CATEGORICAL}, Path(args.ranges))
            print(f"wrote {args.path} (illustrative values, not a benchmark)")
        else:
            {"run": _run, "sweep": _sweep, "lhs": _lhs, "staged": _staged}[args.command](args)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
