<!-- SPDX-FileCopyrightText: Contributors to clean-techs-firm-eu <https://github.com/open-energy-transition/clean-firm-techs-eu/> -->
<!-- SPDX-FileCopyrightText: Open Energy Transition gGmbH -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->

The clean-firm-tech-eu repository is a reproducible modelling study that assesses the value of advanced clean firm technologies in Europe considering a decarbonisation pathway. It has been developed on top of the PyPSA-Eur workflow. 

# Instructions to run the model

## Configuration files

The CATF model is built from stacked config files in `config/catf_model/`. Files listed later override earlier ones.

| File | Purpose |
|---|---|
| `config.base.yaml` | Base CATF assumptions (clustering, costs, solver settings, cost sensitivity groups) and the shared run settings (`run.prefix: catf`, scenario file). Always first. |
| `scenarios.yaml` | All scenarios: the initial scenarios (`baseline`, `high-need`, `low-need`) and the individual sensitivities. |
| `config.initial.yaml` | Initial scenario set: picks `baseline`, `high-need` and `low-need` with `run.name`. |
| `config.sensitivity.yaml` | Sensitivity scenario set: picks `baseline` and the individual sensitivities with `run.name`. |
| `config.advanced.yaml` | Advanced-technology scenario set: picks `baseline` and the advanced-technology scenarios with `run.name`. |
| `config.test.yaml` | Optional overlay for quick tests: one week of snapshots, 28 time segments, `run.prefix: test`. |

All scenario sets share one prefix (`catf`) and one scenario file. A run that is in several sets, such as `baseline`, is solved only once and reused. The set overlays only choose the runs (`run.name`) and the folder of the comparison plots (`catf_model.post_processing.comparison`). Settings that change a run belong in `scenarios.yaml`, not in an overlay; otherwise the run would be rebuilt.

### Initial scenarios

- **baseline**: default PyPSA-Eur demand response; baseline costs.
- **high-need**: investment costs of established technologies (solar, wind, batteries, gas plants) and the gas price +33%; household, services and rail electricity load +10%; EV demand response reduced to 25% of BEVs.
- **low-need**: costs and gas price -25%; electricity load -10%; residential heat demand response on.

Biomass plants keep baseline costs in the initial scenarios.

### Sensitivity scenarios

Each scenario changes one assumption and keeps everything else at the baseline. Cost sensitivities are +33% (`high-*`) or -25% (`low-*`).

| Scenarios | What changes |
|---|---|
| `high-solar` / `low-solar` | Solar PV investment costs (utility, tracking, rooftop) and solar's share of the grid connection cost |
| `high-wind` / `low-wind` | Onshore and offshore wind (turbines, substations, grid connections) |
| `high-battery` / `low-battery` | Li-ion battery storage and inverters |
| `high-gas` / `low-gas` | Gas plant investment costs (OCGT, CCGT, central gas CHP) |
| `high-gas-fuel` / `low-gas-fuel` | Gas fuel price |
| `high-biomass` / `low-biomass` | Solid biomass CHP investment costs |
| `high-need-dsm` / `low-need-dsm` | EV demand response at 25% of BEVs / residential heat demand response on |
| `high-demand` / `low-demand` | Household, services and rail electricity load +10% / -10% |

The technologies in each cost group are listed under `catf_model.cost_sensitivity_groups` in `config.base.yaml`. Each scenario, including High Need and Low Need, sets its factors per group in `catf_model.cost_sensitivity`; groups not set keep factor 1.0. Rule `build_cost_sensitivity` (`rules/catf_model/cost_sensitivity.smk`) then builds a cost file for every run at `resources/catf/<scenario>/custom_costs.csv`, on top of the baseline cost factors (`catf_model.cost_factors`, e.g. solar +30%).

### Advanced-technology scenarios

Each scenario sets a high or low cost case for one advanced technology, following the stakeholder cost assumptions. Costs are given as absolute values per technology and parameter in `catf_model.cost_overwrites`, in the units of the technology-data cost files, and apply in the cost years of `catf_model.cost_overwrite_years` (2040 and 2050, with equal costs). How a value is derived (e.g. `1.25x PyPSA 2040`) is noted in a comment next to it.

| Scenarios | What changes |
|---|---|
| `high-nuclear` / `low-nuclear` | New-build nuclear investment cost 8880 / 6490 EUR/kW and financial lifetime 40 / 60 years |


## Running with pixi tasks

The tasks are defined in `pixi.toml` under `[feature.catf-model.tasks]` and run in the `catf-model` environment. Each one takes an optional scenario set, `initial` (default) or `sensitivity`. This picks `config/catf_model/config.<set>.yaml`.

| Task | What it does |
|---|---|
| `catf-solve [set]` | Solves all scenarios of the set (`solve_networks`). |
| `catf-postprocess [set]` | Runs CATF post-processing (`catf_post_processing`) on the solved scenarios. |
| `catf-test [set]` | Solves and post-processes the set with the `config.test.yaml` overlay (one week, 28 segments; outputs under `results/test/`). |

Run the test version first to check the workflow end to end:

```bash
pixi run -e catf-model catf-test
```

```bash
pixi run -e catf-model catf-test sensitivity
```

Initial scenarios, then post-processing:

```bash
pixi run -e catf-model catf-solve
```

```bash
pixi run -e catf-model catf-postprocess
```

Sensitivity scenarios, then post-processing:

```bash
pixi run -e catf-model catf-solve sensitivity
```

```bash
pixi run -e catf-model catf-postprocess sensitivity
```

Extra Snakemake flags go after `--`. Without it, pixi stops with "received more arguments than expected". For example, a dry run that lists the jobs without running them:

```bash
pixi run -e catf-model catf-solve sensitivity -- -n
```

Outputs are written under `resources/<prefix>/` and `results/<prefix>/`, with `<prefix>` being `catf` or `test`. Each scenario gets its own subfolder. The plots comparing the runs of a set are written to `results/<prefix>/comparison_plots/<set>/`, e.g. `results/catf/comparison_plots/initial/`.

Run the sets one after the other, not at the same time: both include `baseline`, and two Snakemake processes must not build the same files. A set started after another reuses the runs that are already solved.

### Comparing other runs

To compare another selection of runs, add an overlay like `config.initial.yaml` with its own `run.name` and `catf_model.post_processing.comparison`. Runs already solved under the prefix are reused.

## Running on a SLURM cluster

Locally, the pixi tasks run every job on the current machine (`-call` uses all cores). On a SLURM cluster, the `profiles/catf_slurm` profile submits each Snakemake job as its own `sbatch` job instead. The solves for each scenario and planning horizon do not depend on each other, so they run in parallel. With 16 sensitivity scenarios this makes the biggest difference. Scenario-independent steps (clustering, renewable availability, etc.) are shared between scenarios and run only once (`run.shared_resources.policy: base`).

### Starting a run

Run Snakemake from a login node inside `tmux` or `screen`. It has to stay alive for the whole run to submit and track jobs.

```bash
tmux new -s catf
```

Add `--profile profiles/catf_slurm` after `--` to any pixi task:

```bash
pixi run -e catf-model catf-test -- --profile profiles/catf_slurm
```

```bash
pixi run -e catf-model catf-solve -- --profile profiles/catf_slurm
```

```bash
pixi run -e catf-model catf-solve sensitivity -- --profile profiles/catf_slurm
```
