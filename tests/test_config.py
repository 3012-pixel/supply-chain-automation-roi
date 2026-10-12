"""Tests for input loading and validation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from scroi.config import InputError, load_scenario, scenario_from_dict
from tests.conftest import DATA_DIR


@pytest.mark.parametrize("name", ["agv_fleet.yaml", "goods_to_person_picking.yaml", "sortation_retrofit.csv"])
def test_bundled_examples_load_and_are_synthetic(name: str) -> None:
    s = load_scenario(DATA_DIR / "scenarios" / name)
    assert s.synthetic is True
    assert s.capex > 0 and s.project_life_years >= 1


def test_csv_nested_keys_and_ramp() -> None:
    s = load_scenario(DATA_DIR / "scenarios" / "sortation_retrofit.csv")
    assert s.ramp_up == (0.5, 1.0)
    assert s.throughput.capacity_cap_units_per_year == 1_550_000


def test_missing_required_field() -> None:
    with pytest.raises(InputError, match="capex"):
        scenario_from_dict({"name": "x", "project_life_years": 5, "discount_rate": 0.1,
                            "annual_labour_savings": 1})


def test_unknown_field_rejected() -> None:
    with pytest.raises(InputError, match="unknown"):
        scenario_from_dict({"name": "x", "capex": 1, "project_life_years": 5, "discount_rate": 0.1,
                            "annual_labour_savings": 1, "capexx": 2})


@pytest.mark.parametrize("changes", [
    {"capex": -1.0}, {"project_life_years": 0}, {"discount_rate": -1.0}, {"ramp_up": (1.2,)},
])
def test_validation_errors(simple_scenario, changes) -> None:
    with pytest.raises(InputError):
        replace(simple_scenario, **changes)


def test_unsupported_extension(tmp_path) -> None:
    p = tmp_path / "x.json"
    p.write_text("{}")
    with pytest.raises(InputError, match="unsupported"):
        load_scenario(p)
