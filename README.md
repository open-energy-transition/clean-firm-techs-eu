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
| `config.test.yaml` | Optional overlay for quick tests: one week of snapshots, 28 time segments, `run.prefix: test`. |

All scenario sets share one prefix (`catf`) and one scenario file. A run that is in several sets, such as `baseline`, is solved only once and reused. The set overlays only choose the runs (`run.name`) and the folder of the comparison plots (`catf_model.post_processing.comparison`). Settings that change a run belong in `scenarios.yaml`, not in an overlay; otherwise the run would be rebuilt.

## Scenario sets

The scenarios are grouped into three sets. Each set is compared to the same `baseline`, but asks a different question:

| Set | Question | Runs | What changes from the baseline |
|---|---|---|---|
| Initial (`config.initial.yaml`) | How does the system change if conditions are favourable or unfavourable overall? | `high-need`, `low-need` | Several assumptions at once: costs of established technologies, gas price, electricity demand and demand response |
| Sensitivity (`config.sensitivity.yaml`) | Which single assumption of the initial scenarios matters most? | 16 runs, `high-*` / `low-*` | One assumption at a time |
| Advanced (in preparation) | What is the value of each advanced clean firm technology? | 10 runs, `high-*` / `low-*` | One advanced technology made available, with high or low costs |

In the baseline, the initial and the sensitivity scenarios, the advanced technologies are not available.

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

### Advanced technology scenarios (in preparation)

Each scenario makes one advanced technology available and keeps everything else at the baseline. Following the stakeholder cost assumptions, the technologies can only be built from 2040, and their costs are the same in 2040 and 2050.

| Scenarios | Technology | High costs | Low costs |
|---|---|---|---|
| `high-nuclear` / `low-nuclear` | New nuclear | 8,880 EUR/kW, financial lifetime 40 years | 6,490 EUR/kW, 60 years |
| `high-egs` / `low-egs` | Enhanced geothermal | Near-term costs | Subsurface costs -50%, surface costs -15% |
| `high-ccs` / `low-ccs` | Carbon capture (power, industry, SMR) and direct air capture | Capture: PyPSA 2040 +25%; DAC: PyPSA 2025 | Capture: PyPSA 2040 -20%; DAC: PyPSA 2040 |
| `high-hydrogen` / `low-hydrogen` | Electrolysis and fuel cells | PyPSA 2040 | PyPSA 2040 -40% |
| `high-iron-air` / `low-iron-air` | Iron-air storage | PyPSA 2025 (~3,000 EUR/kW) | PyPSA 2040 (~1,400 EUR/kW) |

In both nuclear scenarios, the existing nuclear plants also run for 80 years. Unlike the new technologies, this already applies from 2030.

### Cost groups

The technologies in each cost group are listed under `catf_model.cost_sensitivity_groups` in `config.base.yaml`. Each scenario, including High Need and Low Need, sets its factors per group in `catf_model.cost_sensitivity`; groups not set keep factor 1.0. Rule `build_cost_sensitivity` (`rules/catf_model/cost_sensitivity.smk`) then builds a cost file for every run at `resources/catf/<scenario>/custom_costs.csv`, on top of the baseline cost factors (`catf_model.cost_factors`, e.g. solar +30%).

Instead of a factor, a group can be set with a dict:

- `factor`: multiplier (default 1.0);
- `year`: technology-data year to take the values from, used for all planning horizons;
- `value`: absolute value in the unit of the cost row, only for groups with a single row.

A lifetime is a cost row too, so it is set with its own group of parameter `lifetime` and a `value`. For example, groups in `config.base.yaml`:

```yaml
catf_model:
  cost_sensitivity_groups:
    hydrogen:
      investment: [electrolysis, fuel cell]
    nuclear:
      investment: [nuclear]
    nuclear-lifetime:
      lifetime: [nuclear]
```

and a scenario in `scenarios.yaml`:

```yaml
low-advanced-example:
  catf_model:
    cost_sensitivity:
      hydrogen: {factor: 0.6, year: 2040}  # 2040 costs -40%, also in 2030 and 2050
      nuclear: {value: 6490}               # EUR/kW_e, the unit of the cost row
      nuclear-lifetime: {value: 60}        # years
```

give these rows in `resources/catf/low-advanced-example/custom_costs.csv` (shown for 2050; the values are the same in every planning horizon):

| technology | parameter | value | further description |
|---|---|---|---|
| electrolysis | investment | 905.28 | costs_2040 value 1508.8015 scaled by 0.6 (group hydrogen) |
| fuel cell | investment | 761.41 | costs_2040 value 1269.0130 scaled by 0.6 (group hydrogen) |
| nuclear | investment | 6490 | costs_2050 value 10805.7038 set to 6490 (group nuclear) |
| nuclear | lifetime | 60 | costs_2050 value 40.0000 set to 60 (group nuclear-lifetime) |

A cost row only sets the costs; whether a technology can be built is set by the model switches (e.g. `sector: electrolysis`).


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
