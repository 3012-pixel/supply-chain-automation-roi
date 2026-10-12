# Data

**All data in this folder is synthetic.** The figures are made up to illustrate the model.
They are not benchmarks and do not come from any real company or vendor quote.

| File | Purpose |
|------|---------|
| `scenarios/agv_fleet.yaml` | AGV pallet-move business case (YAML input) |
| `scenarios/goods_to_person_picking.yaml` | Large picking automation case, with custom best/worst multipliers |
| `scenarios/sortation_retrofit.csv` | Marginal small-site case (CSV input, dot-notation for nested keys) |
| `automation_options.csv` | Candidate projects for the portfolio optimiser |
| `portfolio.yaml` | Budget, space and discount-rate constraints for the optimiser |

`exclusive_group` in `automation_options.csv` marks mutually exclusive alternatives
(for example a small *or* a large AGV fleet, not both).
