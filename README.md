<!-- SPDX-FileCopyrightText: Contributors to clean-techs-firm-eu <https://github.com/open-energy-transition/clean-firm-techs-eu/> -->
<!-- SPDX-FileCopyrightText: Open Energy Transition gGmbH -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->

The clean-firm-tech-eu repository is a reproducible modelling study that assesses the value of advanced clean firm technologies in Europe considering a decarbonisation pathway. It has been developed on top of the PyPSA-Eur workflow. 

# Instructions to run the model

## Configuration files

The CATF model is built from stacked config files in `config/catf_model/`. Files listed later override earlier ones.

| File | Purpose |
|---|---|
| `config.base.yaml` | Base CATF assumptions (clustering, costs, solver settings, cost sensitivity groups). Always first. |
| `config.initial.yaml` | Turns on the initial scenario set (`run.prefix: initial`, `run.name: all`) defined in `scenarios.initial.yaml`. |
| `scenarios.initial.yaml` | Initial scenarios: `baseline`, `high-need`, `low-need`. |
| `config.sensitivity.yaml` | Turns on the sensitivity scenario set (`run.prefix: sensitivity`, `run.name: all`) defined in `scenarios.sensitivity.yaml`. |
| `scenarios.sensitivity.yaml` | Individual sensitivities: one technology group, demand or flexibility setting changed at a time. |
| `config.test.yaml` | Optional overlay for quick tests: one week of snapshots, 28 time segments, `run.prefix: test`. |

### Initial scenarios

- **baseline**: default PyPSA-Eur demand response; cost file `custom_costs_x1.0.csv`.
- **high-need**: investment costs of established technologies and the gas price +33% (`x1.33`); household, services and rail electricity load +10%; EV demand response reduced to 25% of BEVs.
- **low-need**: costs and gas price -25% (`x0.75`); electricity load -10%; residential heat demand response on.

The scaled cost files are built by rule `build_cost_sensitivity` (`rules/catf_model/cost_sensitivity.smk`), which reads the factor from the file name and applies it to all groups in `catf_model.cost_sensitivity_groups`.

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

The technologies in each cost group are listed under `catf_model.cost_sensitivity_groups` in `config.base.yaml`. Each scenario sets its factors per group in `catf_model.cost_sensitivity`. Rule `build_scenario_cost_sensitivity` then builds a cost file for that scenario at `resources/sensitivity/<scenario>/custom_costs_sensitivity.csv`.


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

Outputs are written under `resources/<prefix>/` and `results/<prefix>/`, with `<prefix>` being `initial`, `sensitivity` or `test`. Each scenario gets its own subfolder.

### Running a subset of scenarios

`config.initial.yaml` and `config.sensitivity.yaml` set `run.name: all`, which runs every scenario in the matching scenarios file. To run only some of them, change `run.name` to a list:

```yaml
run:
  name:
  - high-solar
  - low-solar
```

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
