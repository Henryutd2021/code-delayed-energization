"""Reading and writing scenario files (JSON) and result tables (CSV).

A scenario file has the four groups of :mod:`code_delay.parameters`; units are part of
the field names. Unknown or missing fields, non-finite values and out-of-range values
raise ``ValueError`` naming the file and the field. Schema: docs/data_pipeline.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

import pandas as pd

from .parameters import PrivateInputs, Project, RatepayerInputs, Scenario

TOP_LEVEL = {"name", "delay_months", "discount_rate_annual", "project", "private", "ratepayer"}
GROUPS = {"project": Project, "private": PrivateInputs, "ratepayer": RatepayerInputs}


def _group(cls, data: Any, label: str):
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be an object")
    allowed = {f.name for f in fields(cls)}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown field(s) {sorted(unknown)}")
    try:
        return cls(**data)
    except TypeError as exc:   # missing required fields
        raise ValueError(f"{label}: {exc}") from None


def scenario_from_dict(data: dict[str, Any], source: str = "scenario") -> Scenario:
    """Build and validate a :class:`Scenario` from a plain dictionary."""
    if not isinstance(data, dict):
        raise ValueError(f"{source}: the top level must be an object")
    unknown = set(data) - TOP_LEVEL
    missing = (TOP_LEVEL - {"name"}) - set(data)
    if unknown:
        raise ValueError(f"{source}: unknown field(s) {sorted(unknown)}")
    if missing:
        raise ValueError(f"{source}: missing field(s) {sorted(missing)}")
    try:
        groups = {k: _group(cls, data[k], f"{source}: {k}") for k, cls in GROUPS.items()}
        return Scenario(discount_rate_annual=data["discount_rate_annual"], delay_months=data["delay_months"],
                        name=data.get("name", "scenario"), **groups)
    except ValueError as exc:
        msg = str(exc)
        raise ValueError(msg if msg.startswith(source) else f"{source}: {msg}") from None


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    """Plain dictionary of a scenario (optional fields left unset are omitted)."""
    out: dict[str, Any] = {"name": scenario.name, "delay_months": scenario.delay_months,
                           "discount_rate_annual": scenario.discount_rate_annual}
    for k in GROUPS:
        out[k] = {f: v for f, v in asdict(getattr(scenario, k)).items() if v is not None}
    return out


def read_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        try:
            data = json.load(fh, parse_constant=lambda c: float(c))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from None
    return scenario_from_dict(data, source=str(path))


def write_scenario(scenario: Scenario, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scenario_to_dict(scenario), indent=2) + "\n", encoding="utf-8")


def read_json(path: str | Path) -> Any:
    """Read an auxiliary JSON file (grid, ranges, cases)."""
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from None


def write_table(table: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)
