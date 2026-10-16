"""Matplotlib charts: tornado and cumulative cash-flow profile."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend; must be set before pyplot import
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

LOW_COLOUR = "#2a6f97"
HIGH_COLOUR = "#e07a1f"


def _money(currency: str) -> FuncFormatter:
    return FuncFormatter(lambda v, _: f"{currency} {v / 1e3:,.0f}k")


def plot_tornado(tornado_df: pd.DataFrame, path: str | Path, currency: str = "EUR",
                 swing: float = 0.20, title: str = "") -> Path:
    """Save a tornado chart of NPV sensitivity and return the file path."""
    path = Path(path)
    df = tornado_df.iloc[::-1]  # widest bar on top
    base = float(df["base_npv"].iloc[0])
    fig, ax = plt.subplots(figsize=(8, 0.6 * len(df) + 1.8), dpi=150)
    y = range(len(df))
    ax.barh(y, df["npv_low_setting"] - base, left=base, color=LOW_COLOUR, label=f"Driver -{swing:.0%}")
    ax.barh(y, df["npv_high_setting"] - base, left=base, color=HIGH_COLOUR, label=f"Driver +{swing:.0%}")
    ax.axvline(base, color="#333", linewidth=1)
    ax.set_yticks(list(y), df["label"])
    ax.xaxis.set_major_formatter(_money(currency))
    ax.set_xlabel("Project NPV")
    ax.set_title(title or f"NPV sensitivity (base NPV {currency} {base:,.0f})", fontsize=11)
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_cumulative_cash_flow(cash_flows: pd.DataFrame, path: str | Path, currency: str = "EUR",
                              title: str = "") -> Path:
    """Save cumulative (undiscounted and discounted) cash-flow lines."""
    path = Path(path)
    fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
    ax.plot(cash_flows["year"], cash_flows["cumulative_cash_flow"], marker="o", color=HIGH_COLOUR,
            label="Cumulative cash flow")
    ax.plot(cash_flows["year"], cash_flows["cumulative_discounted_cash_flow"], marker="o", color=LOW_COLOUR,
            label="Cumulative discounted cash flow")
    ax.axhline(0, color="#333", linewidth=1)
    ax.yaxis.set_major_formatter(_money(currency))
    ax.set_xlabel("Year")
    ax.set_title(title or "Payback profile", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
