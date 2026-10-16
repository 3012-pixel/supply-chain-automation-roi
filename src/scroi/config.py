"""Input models and loaders for automation business cases.

Scenarios can be defined in YAML (nested) or in a two-column CSV
(``parameter,value``) where nested keys use dot notation, e.g.
``throughput.gain_pct``. All bundled example data is SYNTHETIC.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Default base/best/worst scenario multipliers, applied to the base case.
# Keys are driver names understood by ``scroi.sensitivity.apply_driver``.
DEFAULT_SCENARIOS: dict[str, dict[str, float]] = {
    "Worst": {"capex": 1.15, "savings": 0.80, "discount_rate": 1.20, "throughput_gain": 0.50},
    "Base": {},
    "Best": {"capex": 0.95, "savings": 1.10, "discount_rate": 0.90, "throughput_gain": 1.25},
}


class InputError(ValueError):
    """Raised when scenario inputs are missing or invalid."""


@dataclass(frozen=True)
class ThroughputInputs:
    """Throughput uplift from automation, limited by a physical capacity cap.

    Attributes:
        baseline_units_per_year: Units handled per year before automation.
        gain_pct: Fractional throughput gain from automation (0.08 = +8%).
        contribution_margin_per_unit: Contribution earned per extra unit.
        capacity_cap_units_per_year: Hard ceiling (dock doors, outbound
            lanes, etc.). ``None`` means unconstrained.
    """

    baseline_units_per_year: float = 0.0
    gain_pct: float = 0.0
    contribution_margin_per_unit: float = 0.0
    capacity_cap_units_per_year: float | None = None


@dataclass(frozen=True)
class ScenarioInputs:
    """All inputs needed to evaluate one automation investment.

    Monetary values are in ``currency`` per year unless stated otherwise.
    Labour savings are a positive number for a cost *reduction*.
    """

    name: str
    capex: float
    project_life_years: int
    discount_rate: float
    annual_labour_savings: float
    annual_opex_savings: float = 0.0
    annual_maintenance_cost: float = 0.0
    labour_cost_escalation: float = 0.0
    throughput: ThroughputInputs = field(default_factory=ThroughputInputs)
    ramp_up: tuple[float, ...] = (1.0,)
    salvage_value: float = 0.0
    currency: str = "EUR"
    description: str = ""
    synthetic: bool = True
    scenarios: dict[str, dict[str, float]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_SCENARIOS.items()}
    )

    def __post_init__(self) -> None:
        validate(self)


def validate(s: ScenarioInputs) -> None:
    """Validate scenario inputs, raising :class:`InputError` on problems."""
    if s.capex < 0:
        raise InputError("capex must be >= 0")
    if int(s.project_life_years) != s.project_life_years or s.project_life_years < 1:
        raise InputError("project_life_years must be a positive integer")
    if s.discount_rate <= -1:
        raise InputError("discount_rate must be > -100%")
    if not s.ramp_up or any(not 0 <= r <= 1 for r in s.ramp_up):
        raise InputError("ramp_up values must be between 0 and 1")
    if s.annual_maintenance_cost < 0:
        raise InputError("annual_maintenance_cost must be >= 0")
    t = s.throughput
    if t.baseline_units_per_year < 0 or t.contribution_margin_per_unit < 0:
        raise InputError("throughput baseline and margin must be >= 0")
    if t.capacity_cap_units_per_year is not None and t.capacity_cap_units_per_year < 0:
        raise InputError("capacity_cap_units_per_year must be >= 0")


def scenario_from_dict(data: dict[str, Any]) -> ScenarioInputs:
    """Build a :class:`ScenarioInputs` from a (possibly nested) mapping."""
    data = dict(data)
    required = ["name", "capex", "project_life_years", "discount_rate", "annual_labour_savings"]
    missing = [k for k in required if k not in data]
    if missing:
        raise InputError(f"missing required inputs: {', '.join(missing)}")

    tp = data.pop("throughput", None) or {}
    cap = tp.get("capacity_cap_units_per_year")
    throughput = ThroughputInputs(
        baseline_units_per_year=float(tp.get("baseline_units_per_year", 0.0)),
        gain_pct=float(tp.get("gain_pct", 0.0)),
        contribution_margin_per_unit=float(tp.get("contribution_margin_per_unit", 0.0)),
        capacity_cap_units_per_year=None if cap in (None, "") else float(cap),
    )

    ramp = data.pop("ramp_up", (1.0,))
    if isinstance(ramp, str):
        ramp = [x for x in ramp.replace(",", ";").split(";") if x.strip()]
    if isinstance(ramp, (int, float)):
        ramp = [ramp]

    scenarios = data.pop("scenarios", None)
    if scenarios is None:
        scenarios = {k: dict(v) for k, v in DEFAULT_SCENARIOS.items()}

    known = {f for f in ScenarioInputs.__dataclass_fields__} - {"throughput", "ramp_up", "scenarios"}
    unknown = set(data) - known
    if unknown:
        raise InputError(f"unknown inputs: {', '.join(sorted(unknown))}")

    floats = [
        "capex", "discount_rate", "annual_labour_savings", "annual_opex_savings",
        "annual_maintenance_cost", "labour_cost_escalation", "salvage_value",
    ]
    for key in floats:
        if key in data:
            data[key] = float(data[key])
    data["project_life_years"] = int(float(data["project_life_years"]))
    if "synthetic" in data and isinstance(data["synthetic"], str):
        data["synthetic"] = data["synthetic"].strip().lower() in {"true", "1", "yes"}

    return ScenarioInputs(
        throughput=throughput,
        ramp_up=tuple(float(r) for r in ramp),
        scenarios={str(k): {dk: float(dv) for dk, dv in (v or {}).items()} for k, v in scenarios.items()},
        **data,
    )


def _unflatten(rows: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in rows.items():
        node = out
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


def load_scenario(path: str | Path) -> ScenarioInputs:
    """Load a scenario from a ``.yaml``/``.yml`` or ``.csv`` file."""
    path = Path(path)
    if not path.exists():
        raise InputError(f"file not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    elif suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or not {"parameter", "value"} <= set(reader.fieldnames):
                raise InputError("CSV must have 'parameter' and 'value' columns")
            data = _unflatten({r["parameter"].strip(): r["value"].strip() for r in reader if r["parameter"]})
    else:
        raise InputError(f"unsupported file type: {suffix}")
    if not isinstance(data, dict):
        raise InputError("scenario file must contain a mapping")
    return scenario_from_dict(data)
