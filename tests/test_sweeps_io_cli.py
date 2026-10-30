"""Scenario sets, the data interface, the command line and the minimal example."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from code_delay import (evaluate, full_factorial, get_parameter, latin_hypercube, percentiles_by, private_cost,
                        rank_correlations, read_scenario, sample_scenarios, scenario_from_dict, scenario_to_dict,
                        set_parameter, set_parameters, tariff_cases, write_scenario)
from code_delay.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_set_and_get_parameter(scenario):
    s = set_parameter(scenario, "private.operating_margin", 0.45)
    assert get_parameter(s, "private.operating_margin") == 0.45
    assert get_parameter(scenario, "private.operating_margin") == 0.3          # original unchanged
    assert get_parameter(set_parameter(scenario, "delay_months", 9), "delay_months") == 9
    for bad in ("private.unknown", "nogroup.x", "a.b.c", "unknown"):
        with pytest.raises(KeyError):
            set_parameter(scenario, bad, 1)
    with pytest.raises(ValueError):
        set_parameter(scenario, "private.operating_margin", 1.5)               # validated on creation


def test_full_factorial(scenario):
    grid = {"delay_months": [9, 18], "private.deployment_profile": ["static", "linear", "back_loaded"]}
    cases = full_factorial(scenario, grid)
    assert len(cases) == 6
    assert {(c.delay_months, c.private.deployment_profile) for c in cases} == \
        {(t, p) for t in (9, 18) for p in ("static", "linear", "back_loaded")}
    table = evaluate(cases, parameters=list(grid))
    assert table.shape[0] == 6 and {"private_usd", "ratepayer_delay_usd"} <= set(table.columns)
    assert table.private_usd.iloc[0] == pytest.approx(private_cost(cases[0])["total"])
    assert full_factorial(scenario, {}) == [scenario]
    with pytest.raises(ValueError):
        full_factorial(scenario, {"delay_months": []})
    pct = percentiles_by(table, "delay_months", "private_usd", quantiles=(0.5,))
    assert list(pct.columns) == ["delay_months", "p50"]


def test_latin_hypercube_strata():
    u = latin_hypercube(50, 3, seed=3)
    assert u.shape == (50, 3)
    for j in range(3):
        assert sorted(np.floor(u[:, j] * 50).astype(int).tolist()) == list(range(50))
    assert np.array_equal(u, latin_hypercube(50, 3, seed=3))
    assert not np.array_equal(u, latin_hypercube(50, 3, seed=4))
    with pytest.raises(ValueError):
        latin_hypercube(0, 3, seed=1)


def test_sample_scenarios_and_rank_correlations(scenario):
    ranges = {"private.operating_margin": (0.12, 0.48), "ratepayer.residual_share": (0.0, 1.0)}
    cats = {"private.deployment_profile": ["static", "back_loaded"]}
    cases = sample_scenarios(scenario, ranges, 200, seed=11, categorical=cats)
    table = evaluate(cases, parameters=list(ranges) + list(cats))
    assert table["private.operating_margin"].between(0.12, 0.48).all()
    assert set(table["private.deployment_profile"]) == {"static", "back_loaded"}
    corr = rank_correlations(table, list(ranges), ["private_usd", "ratepayer_level_usd"], categorical=list(cats))
    direct = table["private.operating_margin"].rank().corr(table["private_usd"].rank())
    got = corr[(corr.target == "private_usd") & (corr.input == "private.operating_margin")].spearman.iloc[0]
    assert got == pytest.approx(direct)
    assert got > 0
    rp = corr[(corr.target == "ratepayer_level_usd") & (corr.input == "ratepayer.residual_share")].spearman.iloc[0]
    assert rp > 0.9
    assert {"private.deployment_profile_static", "private.deployment_profile_back_loaded"} <= set(corr.input)
    const = table.assign(constant=1.0)
    out = rank_correlations(const, ["private.operating_margin"], ["constant"])
    assert np.isnan(out.spearman.iloc[0])                                     # undefined, no warning
    with pytest.raises(ValueError):
        sample_scenarios(scenario, {"private.operating_margin": (0.48, 0.12)}, 10, seed=1)
    with pytest.raises(ValueError, match="both"):
        sample_scenarios(scenario, {"private.operating_margin": (0.12, 0.48)}, 10, seed=1,
                         categorical={"private.operating_margin": [0.22, 0.32]})
    with pytest.raises(ValueError, match="non-empty list"):
        sample_scenarios(scenario, {}, 10, seed=1, categorical={"private.deployment_profile": 3})


def test_tariff_cases(scenario):
    table = tariff_cases(scenario, {"developer_funded": {"ratepayer.residual_share": 0.0}, "base": {}})
    assert table.ratepayer_level_usd.iloc[0] == 0.0 and table.ratepayer_delay_usd.iloc[0] == 0.0
    assert table.private_usd.nunique() == 1
    # a case may switch the financing rule and unset the field that rule does not use, in any order
    for order in ((("ratepayer.financing_probability", None), ("ratepayer.financing_rule", "realization_linked")),
                  (("ratepayer.financing_rule", "realization_linked"), ("ratepayer.financing_probability", None))):
        linked = tariff_cases(scenario, {"linked": dict(order)})
        s = set_parameters(scenario, dict(order))
        assert s.event_probabilities == pytest.approx((0.8, 0.15))
        assert linked.ratepayer_level_usd.iloc[0] > 0
    with pytest.raises(ValueError):
        set_parameter(scenario, "ratepayer.financing_rule", "realization_linked")   # financing_probability still set


def test_json_round_trip(tmp_path, scenario):
    path = tmp_path / "s.json"
    write_scenario(scenario, path)
    assert read_scenario(path) == scenario
    data = json.loads(path.read_text())
    assert "stranding_probability" not in data["ratepayer"]                  # unset optional fields omitted
    assert scenario_from_dict(scenario_to_dict(scenario)) == scenario


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d.update(extra=1), "unknown field"),
    (lambda d: d.pop("delay_months"), "missing field"),
    (lambda d: d["private"].update(colour="red"), "unknown field"),
    (lambda d: d["private"].pop("operating_margin"), "operating_margin"),
    (lambda d: d["private"].update(operating_margin=1.2), "between 0 and 1"),
    (lambda d: d["project"].update(power_factor=1.1), "power_factor"),
    (lambda d: d["private"].update(deployment_profile="flat"), "deployment_profile"),
    (lambda d: d.update(delay_months=2.5), "whole number"),
    (lambda d: d["ratepayer"].update(stranding_probability=0.1), "not used"),
    (lambda d: d["private"].update(gross_value_usd_per_mw_it_month=float("nan")), "finite"),
    (lambda d: d["private"].update(operating_margin="0.3"), "number"),
])
def test_scenario_validation(scenario, mutate, match):
    data = scenario_to_dict(scenario)
    mutate(data)
    with pytest.raises(ValueError, match=match):
        scenario_from_dict(data)


def test_read_scenario_rejects_nan_and_bad_json(tmp_path, scenario):
    path = tmp_path / "s.json"
    text = json.dumps(scenario_to_dict(scenario)).replace('"operating_margin": 0.3', '"operating_margin": NaN')
    path.write_text(text)
    with pytest.raises(ValueError, match="finite"):
        read_scenario(path)
    path.write_text("{")
    with pytest.raises(ValueError, match="not valid JSON"):
        read_scenario(path)


def test_cli_strict_json_for_undefined_dci(tmp_path, scenario):
    for name, s in (("zero_delay", scenario.with_delay(0)), ("zero_capacity", scenario.with_capacity(0.0))):
        path = tmp_path / f"{name}.json"
        write_scenario(s, path)
        assert main(["run", str(path), "--out-dir", str(tmp_path / name)]) == 0
        text = (tmp_path / name / "summary.json").read_text()
        data = json.loads(text, parse_constant=lambda c: pytest.fail(f"non-standard JSON constant {c}"))
        assert data["private_usd_per_mw_it_month"] is None


def test_cli_example_writes_grid_and_ranges(tmp_path):
    scen, grid, ranges = tmp_path / "s.json", tmp_path / "g.json", tmp_path / "r.json"
    assert main(["example", str(scen), "--grid", str(grid), "--ranges", str(ranges)]) == 0
    assert main(["sweep", str(scen), str(grid), "--out", str(tmp_path / "lattice.csv")]) == 0
    assert main(["lhs", str(scen), str(ranges), "--samples", "16", "--seed", "3", "--out-dir", str(tmp_path / "lhs")]) == 0
    assert len(pd.read_csv(tmp_path / "lhs" / "samples.csv")) == 16


@pytest.mark.parametrize("spec", [
    {"continuous": {"private.operating_margin": 0.3}},
    {"continuous": None},
    {"continuous": {"private.operating_margin": [0.1, "x"]}},
    {"continuous": {}, "categorical": {"private.deployment_profile": 3}},
    {"categorical": {}},
    [1, 2],
])
def test_cli_rejects_malformed_ranges(tmp_path, capsys, spec):
    scen, ranges = tmp_path / "s.json", tmp_path / "r.json"
    assert main(["example", str(scen)]) == 0
    ranges.write_text(json.dumps(spec))
    assert main(["lhs", str(scen), str(ranges), "--samples", "4", "--out-dir", str(tmp_path / "lhs")]) == 2
    assert "error" in capsys.readouterr().err


def test_cli(tmp_path, capsys):
    scen = tmp_path / "s.json"
    assert main(["example", str(scen)]) == 0
    assert main(["run", str(scen), "--out-dir", str(tmp_path / "run")]) == 0
    summary = json.loads((tmp_path / "run" / "summary.json").read_text())
    assert summary["private_usd"] == pytest.approx(private_cost(read_scenario(scen))["total"])
    assert "total_usd" not in summary
    assert len(pd.read_csv(tmp_path / "run" / "private_monthly.csv")) == 30
    grid = tmp_path / "grid.json"
    grid.write_text(json.dumps({"delay_months": [9, 18], "private.operating_margin": [0.22, 0.42]}))
    assert main(["sweep", str(scen), str(grid), "--out", str(tmp_path / "lattice.csv")]) == 0
    assert len(pd.read_csv(tmp_path / "lattice.csv")) == 4
    ranges = tmp_path / "ranges.json"
    ranges.write_text(json.dumps({"continuous": {"private.operating_margin": [0.12, 0.48]},
                                  "categorical": {"private.deployment_profile": ["static", "linear"]}}))
    assert main(["lhs", str(scen), str(ranges), "--samples", "20", "--seed", "2", "--out-dir", str(tmp_path / "lhs")]) == 0
    assert len(pd.read_csv(tmp_path / "lhs" / "samples.csv")) == 20
    assert main(["staged", str(scen), "--first-service", "9", "18", "--fractions", "0.6", "1",
                 "--out", str(tmp_path / "staged.csv")]) == 0
    assert len(pd.read_csv(tmp_path / "staged.csv")) == 4
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert main(["run", str(bad)]) == 2
    assert "error" in capsys.readouterr().err


def test_console_script_entry_point(tmp_path):
    out = subprocess.run([sys.executable, "-m", "code_delay.cli", "example", str(tmp_path / "e.json")],
                         capture_output=True, text=True)
    assert out.returncode == 0 and (tmp_path / "e.json").exists()


def test_minimal_example_runs(capsys):
    runpy.run_path(str(ROOT / "examples" / "minimal.py"), run_name="__main__")
    assert "CoDE vector" in capsys.readouterr().out
