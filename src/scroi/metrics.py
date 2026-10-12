"""Investment KPIs: NPV, IRR, simple and discounted payback.

NPV and IRR use ``numpy_financial`` (v1.0 API: ``npv(rate, values)`` and
``irr(values)``). Note that ``npf.npv`` treats ``values[0]`` as occurring
at t=0 (undiscounted), unlike Excel's ``NPV()`` which discounts the first
value.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np
import numpy_financial as npf

from scroi.cashflows import build_cash_flows
from scroi.config import ScenarioInputs


@dataclass(frozen=True)
class KPIs:
    """Headline investment metrics for one scenario."""

    npv: float
    irr: float | None
    simple_payback_years: float | None
    discounted_payback_years: float | None
    profitability_index: float | None
    total_net_cash_flow: float

    def as_dict(self) -> dict[str, float | None]:
        """Return the KPIs as a plain dictionary."""
        return asdict(self)

    @property
    def decision(self) -> str:
        """Simple go/no-go recommendation based on the sign of NPV."""
        return "GO" if self.npv > 0 else "NO-GO"


def npv(rate: float, cash_flows: Sequence[float]) -> float:
    """Net present value with ``cash_flows[0]`` at t=0."""
    return float(npf.npv(rate, list(cash_flows)))


def irr(cash_flows: Sequence[float]) -> float | None:
    """Internal rate of return, or ``None`` if it is undefined.

    IRR is undefined when cash flows never change sign (``npf.irr`` returns NaN).
    """
    value = npf.irr(list(cash_flows))
    return None if value is None or np.isnan(value) else float(value)


def payback_period(cash_flows: Sequence[float]) -> float | None:
    """Years until cumulative cash flow turns non-negative.

    Uses linear interpolation within the crossover year. Returns ``None``
    if the investment never pays back within the horizon.
    """
    cfs = np.asarray(cash_flows, dtype=float)
    cumulative = np.cumsum(cfs)
    if cumulative[0] >= 0:
        return 0.0
    for t in range(1, len(cfs)):
        if cumulative[t] >= 0:
            shortfall = -cumulative[t - 1]
            return (t - 1) + shortfall / cfs[t]
    return None


def compute_kpis(s: ScenarioInputs) -> KPIs:
    """Compute all KPIs for a scenario."""
    df = build_cash_flows(s)
    cfs = df["net_cash_flow"].to_numpy()
    value = npv(s.discount_rate, cfs)
    pi = (value + s.capex) / s.capex if s.capex > 0 else None
    return KPIs(
        npv=value,
        irr=irr(cfs),
        simple_payback_years=payback_period(cfs),
        discounted_payback_years=payback_period(df["discounted_cash_flow"].to_numpy()),
        profitability_index=pi,
        total_net_cash_flow=float(cfs.sum()),
    )
