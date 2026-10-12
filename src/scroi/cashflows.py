"""Annual cash-flow construction for an automation investment."""

from __future__ import annotations

import pandas as pd

from scroi.config import ScenarioInputs, ThroughputInputs


def throughput_benefit(t: ThroughputInputs) -> float:
    """Annual contribution from extra throughput, respecting the capacity cap.

    The uplift is ``min(baseline * (1 + gain), cap) - baseline`` units,
    floored at zero, multiplied by the contribution margin per unit.
    """
    target = t.baseline_units_per_year * (1 + t.gain_pct)
    if t.capacity_cap_units_per_year is not None:
        target = min(target, t.capacity_cap_units_per_year)
    return max(target - t.baseline_units_per_year, 0.0) * t.contribution_margin_per_unit


def ramp_factor(ramp_up: tuple[float, ...], year: int) -> float:
    """Share of steady-state benefits realised in ``year`` (1-indexed).

    Years beyond the ramp profile use its final value.
    """
    if year < 1:
        return 0.0
    return ramp_up[min(year, len(ramp_up)) - 1]


def build_cash_flows(s: ScenarioInputs) -> pd.DataFrame:
    """Build the year-by-year cash-flow table (year 0 = investment).

    Benefits (labour, opex, throughput) are scaled by the ramp-up factor;
    maintenance is incurred in full from year 1. Labour savings escalate
    annually with ``labour_cost_escalation`` (wage inflation makes avoided
    labour more valuable over time). Salvage is received in the final year.
    """
    tp = throughput_benefit(s.throughput)
    rows = []
    for year in range(s.project_life_years + 1):
        if year == 0:
            row = dict(year=0, capex=-s.capex, labour_savings=0.0, opex_savings=0.0,
                       throughput_benefit=0.0, maintenance=0.0, ramp_factor=0.0, salvage=0.0)
        else:
            r = ramp_factor(s.ramp_up, year)
            labour = s.annual_labour_savings * (1 + s.labour_cost_escalation) ** (year - 1)
            row = dict(
                year=year,
                capex=0.0,
                labour_savings=labour * r,
                opex_savings=s.annual_opex_savings * r,
                throughput_benefit=tp * r,
                maintenance=-s.annual_maintenance_cost,
                ramp_factor=r,
                salvage=s.salvage_value if year == s.project_life_years else 0.0,
            )
        rows.append(row)

    df = pd.DataFrame(rows)
    flow_cols = ["capex", "labour_savings", "opex_savings", "throughput_benefit", "maintenance", "salvage"]
    df["net_cash_flow"] = df[flow_cols].sum(axis=1)
    df["discount_factor"] = 1 / (1 + s.discount_rate) ** df["year"]
    df["discounted_cash_flow"] = df["net_cash_flow"] * df["discount_factor"]
    df["cumulative_cash_flow"] = df["net_cash_flow"].cumsum()
    df["cumulative_discounted_cash_flow"] = df["discounted_cash_flow"].cumsum()
    return df
