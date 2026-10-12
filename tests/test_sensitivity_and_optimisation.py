"""Tests for sensitivity analysis and portfolio optimisation."""

from __future__ import annotations

import pandas as pd
import pytest

from scroi.metrics import compute_kpis
from scroi.optimisation import load_portfolio_config, optimise_portfolio, option_npv
from scroi.sensitivity import apply_driver, scenario_table, tornado
from tests.conftest import DATA_DIR


def test_tornado_directions(rich_scenario) -> None:
    df = tornado(rich_scenario, swing=0.2).set_index("driver")
    # Higher capex / discount rate -> lower NPV; higher savings / throughput -> higher NPV
    assert df.loc["capex", "npv_high_setting"] < df.loc["capex", "npv_low_setting"]
    assert df.loc["discount_rate", "npv_high_setting"] < df.loc["discount_rate", "npv_low_setting"]
    assert df.loc["savings", "npv_high_setting"] > df.loc["savings", "npv_low_setting"]
    assert df.loc["throughput_gain", "npv_high_setting"] >= df.loc["throughput_gain", "npv_low_setting"]


def test_tornado_sorted_by_range(rich_scenario) -> None:
    ranges = tornado(rich_scenario)["npv_range"].tolist()
    assert ranges == sorted(ranges, reverse=True)


def test_tornado_bad_swing(rich_scenario) -> None:
    with pytest.raises(ValueError):
        tornado(rich_scenario, swing=1.5)


def test_apply_driver_unknown(rich_scenario) -> None:
    with pytest.raises(ValueError, match="unknown driver"):
        apply_driver(rich_scenario, "nonsense", 1.1)


def test_capex_driver_shifts_npv_exactly(rich_scenario) -> None:
    base = compute_kpis(rich_scenario).npv
    assert compute_kpis(apply_driver(rich_scenario, "capex", 1.1)).npv == pytest.approx(base - 100)


def test_scenario_ordering(rich_scenario) -> None:
    df = scenario_table(rich_scenario).set_index("scenario")
    assert df.loc["Worst", "npv"] < df.loc["Base", "npv"] < df.loc["Best", "npv"]
    assert df.loc["Base", "npv"] == pytest.approx(compute_kpis(rich_scenario).npv)


def _options() -> pd.DataFrame:
    return pd.DataFrame([
        # id, name, capex, footprint, benefit, life, group
        ("A", "A", 100, 10, 40, 5, "g1"),
        ("B", "B", 150, 10, 60, 5, "g1"),
        ("C", "C", 100, 50, 35, 5, ""),
        ("D", "D", 100, 10, 5, 5, ""),  # negative NPV, never chosen
    ], columns=["option_id", "name", "capex", "footprint_m2", "annual_net_benefit", "life_years",
                "exclusive_group"])


def test_option_npv() -> None:
    assert option_npv(100, 30, 2, 0.0) == pytest.approx(-40)


def test_optimiser_respects_exclusivity_and_budget() -> None:
    res = optimise_portfolio(_options(), budget=250, space_m2=100, discount_rate=0.08)
    chosen = set(res.selected["option_id"])
    assert chosen == {"B", "C"}  # best of group g1 plus C, within 250 budget
    assert res.total_capex <= 250 and res.total_footprint_m2 <= 100


def test_optimiser_space_constraint_binds() -> None:
    res = optimise_portfolio(_options(), budget=1000, space_m2=30, discount_rate=0.08)
    assert set(res.selected["option_id"]) == {"B"}  # C needs 50 m2


def test_optimiser_skips_negative_npv() -> None:
    res = optimise_portfolio(_options(), budget=10_000, space_m2=10_000, discount_rate=0.08)
    assert "D" not in set(res.selected["option_id"])


def test_bundled_portfolio_feasible() -> None:
    pc = load_portfolio_config(DATA_DIR / "portfolio.yaml")
    res = optimise_portfolio(pc.options, pc.budget, pc.space_m2, pc.discount_rate)
    assert res.total_capex <= pc.budget and res.total_footprint_m2 <= pc.space_m2
    assert res.total_npv > 0
    per_group = res.selected[res.selected["exclusive_group"] != ""].groupby("exclusive_group").size()
    assert (per_group <= 1).all()
