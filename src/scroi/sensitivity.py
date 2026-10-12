"""One-at-a-time sensitivity (tornado) and base/best/worst scenario analysis."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from scroi.config import ScenarioInputs
from scroi.metrics import compute_kpis

DRIVERS: dict[str, str] = {
    "discount_rate": "Discount rate",
    "savings": "Annual savings (labour + opex)",
    "capex": "Capex",
    "throughput_gain": "Throughput gain",
}


def apply_driver(s: ScenarioInputs, driver: str, multiplier: float) -> ScenarioInputs:
    """Return a copy of ``s`` with one driver scaled by ``multiplier``."""
    if driver == "discount_rate":
        return replace(s, discount_rate=s.discount_rate * multiplier)
    if driver == "savings":
        return replace(
            s,
            annual_labour_savings=s.annual_labour_savings * multiplier,
            annual_opex_savings=s.annual_opex_savings * multiplier,
        )
    if driver == "capex":
        return replace(s, capex=s.capex * multiplier)
    if driver == "throughput_gain":
        return replace(s, throughput=replace(s.throughput, gain_pct=s.throughput.gain_pct * multiplier))
    raise ValueError(f"unknown driver: {driver!r}; expected one of {sorted(DRIVERS)}")


def apply_multipliers(s: ScenarioInputs, multipliers: dict[str, float]) -> ScenarioInputs:
    """Apply several driver multipliers at once."""
    for driver, m in multipliers.items():
        s = apply_driver(s, driver, m)
    return s


def tornado(s: ScenarioInputs, swing: float = 0.20, drivers: list[str] | None = None) -> pd.DataFrame:
    """NPV impact of flexing each driver by ``±swing`` (one at a time).

    Returns one row per driver, sorted by NPV range (widest first), with the
    NPV at the low (``1 - swing``) and high (``1 + swing``) settings.
    """
    if not 0 < swing < 1:
        raise ValueError("swing must be between 0 and 1")
    base_npv = compute_kpis(s).npv
    rows = []
    for d in drivers or list(DRIVERS):
        low = compute_kpis(apply_driver(s, d, 1 - swing)).npv
        high = compute_kpis(apply_driver(s, d, 1 + swing)).npv
        rows.append({
            "driver": d,
            "label": DRIVERS[d],
            "npv_low_setting": low,
            "npv_high_setting": high,
            "base_npv": base_npv,
            "npv_range": abs(high - low),
        })
    return pd.DataFrame(rows).sort_values("npv_range", ascending=False, ignore_index=True)


def scenario_table(s: ScenarioInputs) -> pd.DataFrame:
    """KPIs for each named scenario (default: Worst / Base / Best)."""
    rows = []
    for name, multipliers in s.scenarios.items():
        k = compute_kpis(apply_multipliers(s, multipliers))
        rows.append({"scenario": name, **k.as_dict(), "decision": k.decision,
                     "assumptions": ", ".join(f"{d} x{m:g}" for d, m in multipliers.items()) or "as input"})
    return pd.DataFrame(rows)
