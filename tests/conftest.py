"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from scroi.config import ScenarioInputs, ThroughputInputs

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def simple_scenario() -> ScenarioInputs:
    """Tiny hand-checkable scenario: 100 capex, 60/yr for 2 years at 10%."""
    return ScenarioInputs(
        name="Simple",
        capex=100.0,
        project_life_years=2,
        discount_rate=0.10,
        annual_labour_savings=60.0,
    )


@pytest.fixture
def rich_scenario() -> ScenarioInputs:
    """Scenario exercising ramp-up, escalation, throughput cap and salvage."""
    return ScenarioInputs(
        name="Rich",
        capex=1000.0,
        project_life_years=4,
        discount_rate=0.08,
        annual_labour_savings=300.0,
        annual_opex_savings=50.0,
        annual_maintenance_cost=40.0,
        labour_cost_escalation=0.05,
        throughput=ThroughputInputs(
            baseline_units_per_year=1000,
            gain_pct=0.20,
            contribution_margin_per_unit=1.0,
            capacity_cap_units_per_year=1100,
        ),
        ramp_up=(0.5, 1.0),
        salvage_value=25.0,
    )
