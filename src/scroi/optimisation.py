"""Choose the best mix of automation options under budget and space limits.

Formulated as a 0/1 knapsack-style mixed-integer linear programme and solved
with ``scipy.optimize.milp`` (HiGHS backend):

    maximise    sum_i NPV_i * x_i
    subject to  sum_i capex_i * x_i     <= budget
                sum_i footprint_i * x_i <= space
                sum_{i in g} x_i        <= 1   for each mutually exclusive group g
                x_i in {0, 1}
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import Bounds, LinearConstraint, milp

from scroi.metrics import npv

OPTION_COLUMNS = ["option_id", "name", "capex", "footprint_m2", "annual_net_benefit", "life_years", "exclusive_group"]


@dataclass(frozen=True)
class PortfolioConfig:
    """Constraints and inputs for the portfolio optimisation."""

    options: pd.DataFrame
    budget: float
    space_m2: float
    discount_rate: float
    currency: str = "EUR"


@dataclass(frozen=True)
class OptimisationResult:
    """Result of the portfolio optimisation."""

    options: pd.DataFrame  # all options with npv and a boolean ``selected`` column
    total_npv: float
    total_capex: float
    total_footprint_m2: float
    budget: float
    space_m2: float
    status: str

    @property
    def selected(self) -> pd.DataFrame:
        """Only the selected options."""
        return self.options[self.options["selected"]]


def load_options(path: str | Path) -> pd.DataFrame:
    """Load automation options from CSV and validate required columns."""
    df = pd.read_csv(path)
    missing = set(OPTION_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"options CSV missing columns: {', '.join(sorted(missing))}")
    df["exclusive_group"] = df["exclusive_group"].fillna("").astype(str).str.strip()
    return df[OPTION_COLUMNS].copy()


def load_portfolio_config(path: str | Path) -> PortfolioConfig:
    """Load a portfolio YAML; ``options_csv`` is resolved relative to the YAML."""
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    for key in ("options_csv", "budget", "space_m2", "discount_rate"):
        if key not in data:
            raise ValueError(f"portfolio config missing '{key}'")
    return PortfolioConfig(
        options=load_options(path.parent / data["options_csv"]),
        budget=float(data["budget"]),
        space_m2=float(data["space_m2"]),
        discount_rate=float(data["discount_rate"]),
        currency=str(data.get("currency", "EUR")),
    )


def option_npv(capex: float, annual_net_benefit: float, life_years: int, rate: float) -> float:
    """NPV of a single option with a level annual benefit."""
    return npv(rate, [-capex] + [annual_net_benefit] * int(life_years))


def optimise_portfolio(
    options: pd.DataFrame, budget: float, space_m2: float, discount_rate: float
) -> OptimisationResult:
    """Select the NPV-maximising subset of options (see module docstring)."""
    df = options.copy().reset_index(drop=True)
    df["npv"] = [
        option_npv(r.capex, r.annual_net_benefit, r.life_years, discount_rate) for r in df.itertuples()
    ]
    n = len(df)
    if n == 0:
        raise ValueError("no options supplied")

    rows = [df["capex"].to_numpy(float), df["footprint_m2"].to_numpy(float)]
    ub = [budget, space_m2]
    groups = df["exclusive_group"].fillna("").astype(str)
    for g in sorted(set(groups) - {""}):
        rows.append((groups == g).to_numpy(float))
        ub.append(1.0)

    res = milp(
        c=-df["npv"].to_numpy(float),  # milp minimises
        integrality=np.ones(n),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(np.vstack(rows), -np.inf, np.array(ub)),
    )
    if res.x is None:
        raise RuntimeError(f"optimisation failed: {res.message}")

    df["selected"] = np.round(res.x).astype(bool)
    sel = df[df["selected"]]
    return OptimisationResult(
        options=df,
        total_npv=float(sel["npv"].sum()),
        total_capex=float(sel["capex"].sum()),
        total_footprint_m2=float(sel["footprint_m2"].sum()),
        budget=budget,
        space_m2=space_m2,
        status=str(res.message),
    )
