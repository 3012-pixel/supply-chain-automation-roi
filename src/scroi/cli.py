"""Command-line interface.

Examples::

    scroi evaluate data/scenarios/agv_fleet.yaml --portfolio data/portfolio.yaml
    scroi compare data/scenarios/*.yaml
    scroi optimise data/portfolio.yaml --budget 3000000
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from scroi.cashflows import build_cash_flows
from scroi.charts import plot_cumulative_cash_flow, plot_tornado
from scroi.config import InputError, load_scenario
from scroi.metrics import KPIs, compute_kpis
from scroi.optimisation import OptimisationResult, load_portfolio_config, optimise_portfolio
from scroi.report import write_excel_report
from scroi.sensitivity import scenario_table, tornado


def _missing(v: float | None) -> bool:
    """True for None or NaN (pandas turns None into NaN in float columns)."""
    return v is None or pd.isna(v)


def _fmt_money(v: float | None, cur: str) -> str:
    return "n/a" if _missing(v) else f"{cur} {v:,.0f}"


def _fmt_pct(v: float | None) -> str:
    return "n/a" if _missing(v) else f"{v:.1%}"


def _fmt_years(v: float | None) -> str:
    return "never" if _missing(v) else f"{v:.2f} yrs"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _print_kpis(name: str, k: KPIs, cur: str) -> None:
    print(f"\n=== {name} ===")
    print(f"  NPV                : {_fmt_money(k.npv, cur)}")
    print(f"  IRR                : {_fmt_pct(k.irr)}")
    print(f"  Simple payback     : {_fmt_years(k.simple_payback_years)}")
    print(f"  Discounted payback : {_fmt_years(k.discounted_payback_years)}")
    pi = "n/a" if k.profitability_index is None else f"{k.profitability_index:.2f}"
    print(f"  Profitability index: {pi}")
    print(f"  Recommendation     : {k.decision}")


def _print_optimisation(o: OptimisationResult, cur: str) -> None:
    print("\n=== Portfolio optimisation ===")
    print(f"  Budget used : {_fmt_money(o.total_capex, cur)} of {_fmt_money(o.budget, cur)}")
    print(f"  Space used  : {o.total_footprint_m2:,.0f} of {o.space_m2:,.0f} m2")
    print(f"  Total NPV   : {_fmt_money(o.total_npv, cur)}")
    cols = ["option_id", "name", "capex", "footprint_m2", "npv"]
    print(o.selected[cols].to_string(index=False, float_format=lambda x: f"{x:,.0f}"))


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Evaluate one scenario and write the Excel report and charts."""
    s = load_scenario(args.scenario)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    slug = _slug(s.name)

    cf = build_cash_flows(s)
    k = compute_kpis(s)
    tor = tornado(s, swing=args.swing)
    scen = scenario_table(s)

    opt = None
    if args.portfolio:
        pc = load_portfolio_config(args.portfolio)
        opt = optimise_portfolio(pc.options, pc.budget, pc.space_m2, pc.discount_rate)

    tornado_png = plot_tornado(tor, out / f"{slug}_tornado.png", s.currency, args.swing,
                               title=f"{s.name}: NPV sensitivity (±{args.swing:.0%})")
    payback_png = plot_cumulative_cash_flow(cf, out / f"{slug}_payback.png", s.currency,
                                            title=f"{s.name}: payback profile")
    xlsx = write_excel_report(out / f"{slug}_report.xlsx", s, cf, k, tor, scen, opt,
                              images=[("Sensitivity", tornado_png), ("Cash Flows", payback_png)])

    if s.synthetic:
        print("NOTE: inputs are SYNTHETIC (illustrative only).")
    _print_kpis(s.name, k, s.currency)
    print("\n--- Scenarios ---")
    view = scen[["scenario", "npv", "irr", "discounted_payback_years", "decision"]].copy()
    view["npv"] = view["npv"].map(lambda v: _fmt_money(v, s.currency))
    view["irr"] = view["irr"].map(_fmt_pct)
    view["discounted_payback_years"] = view["discounted_payback_years"].map(_fmt_years)
    print(view.to_string(index=False))
    if opt is not None:
        _print_optimisation(opt, s.currency)
    print(f"\nReport: {xlsx}\nCharts: {tornado_png}, {payback_png}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Print a side-by-side KPI comparison of several scenarios."""
    paths = [p for pattern in args.scenarios for p in (glob.glob(pattern) or [pattern])]
    rows = []
    for p in paths:
        s = load_scenario(p)
        k = compute_kpis(s)
        rows.append({"scenario": s.name, "capex": _fmt_money(s.capex, s.currency),
                     "npv": _fmt_money(k.npv, s.currency), "irr": _fmt_pct(k.irr),
                     "payback": _fmt_years(k.simple_payback_years),
                     "disc_payback": _fmt_years(k.discounted_payback_years), "decision": k.decision})
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


def cmd_optimise(args: argparse.Namespace) -> int:
    """Run only the portfolio optimisation."""
    pc = load_portfolio_config(args.portfolio)
    opt = optimise_portfolio(
        pc.options,
        args.budget if args.budget is not None else pc.budget,
        args.space if args.space is not None else pc.space_m2,
        pc.discount_rate,
    )
    _print_optimisation(opt, pc.currency)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    load_dotenv()
    default_out = os.getenv("SCROI_OUTPUT_DIR", "outputs")
    p = argparse.ArgumentParser(prog="scroi", description="Supply chain automation ROI model.")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("evaluate", help="evaluate one scenario and export an Excel report")
    e.add_argument("scenario", help="scenario file (.yaml/.yml/.csv)")
    e.add_argument("--portfolio", help="portfolio YAML for the optimisation sheet")
    e.add_argument("--out", default=default_out, help=f"output folder (default: {default_out})")
    e.add_argument("--swing", type=float, default=0.20, help="tornado swing, e.g. 0.2 = ±20%%")
    e.set_defaults(func=cmd_evaluate)

    c = sub.add_parser("compare", help="compare KPIs across scenario files")
    c.add_argument("scenarios", nargs="+", help="scenario files or glob patterns")
    c.set_defaults(func=cmd_compare)

    o = sub.add_parser("optimise", help="pick the best mix of automation options")
    o.add_argument("portfolio", help="portfolio YAML")
    o.add_argument("--budget", type=float, help="override budget")
    o.add_argument("--space", type=float, help="override available space (m2)")
    o.set_defaults(func=cmd_optimise)
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (InputError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
