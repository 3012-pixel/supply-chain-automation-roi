"""Tests for cash flows and KPI calculations."""

from __future__ import annotations

import math

import pytest

from scroi.cashflows import build_cash_flows, ramp_factor, throughput_benefit
from scroi.config import ThroughputInputs
from scroi.metrics import compute_kpis, irr, npv, payback_period


def test_npv_matches_hand_calculation() -> None:
    # -100 + 60/1.1 + 60/1.21 = 4.1322...
    assert npv(0.10, [-100, 60, 60]) == pytest.approx(4.132231, rel=1e-6)


def test_irr_simple_case() -> None:
    assert irr([-100, 110]) == pytest.approx(0.10)


def test_irr_undefined_when_no_sign_change() -> None:
    assert irr([100, 10, 10]) is None


def test_payback_interpolates_within_year() -> None:
    # cumulative: -100, -40, +20 -> 1 + 40/60 years
    assert payback_period([-100, 60, 60]) == pytest.approx(1 + 40 / 60)


def test_payback_none_when_never_recovered() -> None:
    assert payback_period([-100, 10, 10]) is None


def test_payback_zero_when_no_investment() -> None:
    assert payback_period([0, 10]) == 0.0


def test_throughput_capacity_cap_binds() -> None:
    t = ThroughputInputs(1000, 0.20, 2.0, capacity_cap_units_per_year=1100)
    assert throughput_benefit(t) == pytest.approx(100 * 2.0)


def test_throughput_uncapped() -> None:
    t = ThroughputInputs(1000, 0.20, 2.0, capacity_cap_units_per_year=None)
    assert throughput_benefit(t) == pytest.approx(200 * 2.0)


def test_throughput_cap_below_baseline_gives_zero() -> None:
    t = ThroughputInputs(1000, 0.20, 2.0, capacity_cap_units_per_year=900)
    assert throughput_benefit(t) == 0.0


def test_ramp_factor_extends_last_value() -> None:
    assert ramp_factor((0.5, 0.8), 1) == 0.5
    assert ramp_factor((0.5, 0.8), 2) == 0.8
    assert ramp_factor((0.5, 0.8), 7) == 0.8


def test_cash_flow_table_components(rich_scenario) -> None:
    df = build_cash_flows(rich_scenario)
    assert list(df["year"]) == [0, 1, 2, 3, 4]
    assert df.loc[0, "net_cash_flow"] == -1000
    # Year 1: ramp 0.5 on (300 labour + 50 opex + 100 throughput), minus 40 maintenance
    assert df.loc[1, "net_cash_flow"] == pytest.approx(0.5 * (300 + 50 + 100) - 40)
    # Year 3: labour escalated twice, full ramp
    assert df.loc[3, "labour_savings"] == pytest.approx(300 * 1.05**2)
    assert df.loc[4, "salvage"] == 25 and df.loc[3, "salvage"] == 0
    assert df["cumulative_cash_flow"].iloc[-1] == pytest.approx(df["net_cash_flow"].sum())


def test_kpis_consistent_with_cash_flows(simple_scenario) -> None:
    k = compute_kpis(simple_scenario)
    assert k.npv == pytest.approx(4.132231, rel=1e-6)
    assert k.irr is not None and npv(k.irr, [-100, 60, 60]) == pytest.approx(0, abs=1e-6)
    assert k.simple_payback_years == pytest.approx(1 + 40 / 60)
    assert k.discounted_payback_years is not None
    assert k.discounted_payback_years > k.simple_payback_years
    assert k.profitability_index == pytest.approx(1.04132231)
    assert k.decision == "GO"


def test_discounted_npv_equals_sum_of_discounted_flows(rich_scenario) -> None:
    df = build_cash_flows(rich_scenario)
    assert compute_kpis(rich_scenario).npv == pytest.approx(df["discounted_cash_flow"].sum())
    assert not math.isnan(df["discount_factor"].iloc[-1])
